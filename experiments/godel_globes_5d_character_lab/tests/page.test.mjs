import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(folder, "index.html"), "utf8");
const app = fs.readFileSync(path.join(folder, "app.js"), "utf8");
const css = fs.readFileSync(path.join(folder, "styles.css"), "utf8");

test("every DOM id requested by the application exists exactly once", () => {
  const authoredIds = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
  assert.equal(new Set(authoredIds).size, authoredIds.length, "HTML contains a duplicate id");
  const requestedIds = Array.from(app.matchAll(/getElementById\("([^"]+)"\)/g), (match) => match[1]);
  requestedIds.forEach((id) => {
    assert.equal(authoredIds.filter((candidate) => candidate === id).length, 1, `missing DOM id ${id}`);
  });
});

test("the standalone page loads only local scripts in dependency order", () => {
  const scripts = Array.from(html.matchAll(/<script src="([^"]+)"/g), (match) => match[1]);
  assert.deepEqual(scripts, ["space.js", "model.js", "study.js", "app.js"]);
  assert.doesNotMatch(html, /https?:\/\//i);
});

test("the flat condition removes the embodiment and anatomy grouping", () => {
  assert.match(css, /body\[data-condition="flat"\] \.stage \{ display: none; \}/);
  assert.match(css, /body\[data-condition="flat"\] \.controls legend \{ display: none; \}/);
});

test("the editor exposes a versioned game-state API and change event", () => {
  assert.match(app, /getState:/);
  assert.match(app, /pixieology:character-state/);
  assert.match(app, /model\.characterState\(current\)/);
});

test("study progress is resumable and incomplete export is disabled", () => {
  assert.match(app, /StudySession\.fromReceipt/);
  assert.match(app, /localStorage\.setItem/);
  assert.match(html, /id="study-export" type="button" disabled/);
  assert.match(app, /studySession\.results\.length !== studyApi\.tasks\.length/);
});
