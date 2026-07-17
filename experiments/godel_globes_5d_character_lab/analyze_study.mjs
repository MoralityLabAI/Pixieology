import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const analysis = require("./study_analysis.js");

const receipts = process.argv.slice(2).map((filename) => {
  const absolute = path.resolve(filename);
  return JSON.parse(fs.readFileSync(absolute, "utf8"));
});

process.stdout.write(`${JSON.stringify(analysis.analyze(receipts), null, 2)}\n`);
