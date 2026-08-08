import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "observatory.css"), "utf8");
const js = fs.readFileSync(path.join(root, "observatory.js"), "utf8");

test("page provides six keyboard-addressable paper tabs", () => {
  const tabs = [...html.matchAll(/data-lens="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(tabs, ["bimt", "clock_pizza", "hypernetwork", "mips", "sid", "open_problems"]);
  assert.match(html, /role="tablist"/);
  assert.match(js, /ArrowLeft/);
  assert.match(js, /ArrowRight/);
});

test("page states its evidence boundary and exposes agent state", () => {
  assert.match(html, /Synthetic method fixture/);
  assert.match(html, /no trained-model result/);
  assert.match(html, /id="agent-snapshot"/);
  assert.match(html, /id="copy-snapshot"/);
});

test("layout has a narrow-screen mode and motion preference", () => {
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /min-width: 320px/);
});

test("all generated SVGs use viewBox semantics", () => {
  const svgStarts = [...js.matchAll(/<svg /g)].length;
  const viewBoxes = [...js.matchAll(/<svg viewBox=/g)].length;
  assert.equal(svgStarts, viewBoxes);
});
