#!/usr/bin/env node
// Vendors the rich-text kit into a site or the dashboard (ADR-0010).
// Usage: node sync-rich-text-kit.mjs <target-dir> [--check]
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const kitRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const { version } = JSON.parse(readFileSync(join(kitRoot, "package.json"), "utf8"));
// Every file in src/ that index.ts transitively imports (no test-only files live in src/).
const FILES = [
  "parse.ts", "href.ts", "whitespace.ts", "detect.ts", "normalize.ts", "serialize.ts", "legacy.ts",
  "plainText.ts", "RichText.tsx", "splitRichWords.tsx", "index.ts", "cms-rich.css",
];
const [target, flag] = process.argv.slice(2);
if (!target) {
  console.error("usage: sync-rich-text-kit.mjs <target-dir> [--check]");
  process.exit(2);
}
const lf = (s) => s.replace(/\r\n/g, "\n");
const header = (f) =>
  f.endsWith(".css")
    ? `/* Vendored from CMS client-kit/rich-text v${version} — do not edit; re-sync instead. */\n`
    : `// Vendored from CMS client-kit/rich-text v${version} — do not edit; re-sync instead.\n`;
const drift = [];
for (const f of FILES) {
  const want = header(f) + lf(readFileSync(join(kitRoot, "src", f), "utf8"));
  const dest = join(target, f);
  if (flag === "--check") {
    if (!existsSync(dest) || lf(readFileSync(dest, "utf8")) !== want) drift.push(f);
  } else {
    mkdirSync(target, { recursive: true });
    writeFileSync(dest, want);
  }
}
const versionFile = join(target, "VERSION");
if (flag === "--check") {
  if (!existsSync(versionFile) || readFileSync(versionFile, "utf8").trim() !== version) drift.push("VERSION");
  if (drift.length) {
    console.error(`rich-text kit drift in ${target}: ${drift.join(", ")} — run the sync script`);
    process.exit(1);
  }
  console.log(`rich-text kit v${version} in sync: ${target}`);
} else {
  writeFileSync(versionFile, `${version}\n`);
  console.log(`synced rich-text kit v${version} -> ${target}`);
}
