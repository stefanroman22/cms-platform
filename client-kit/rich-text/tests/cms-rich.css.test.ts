// @ts-nocheck — this project has no @types/node (it's a browser-facing kit;
// tsconfig's lib is ES2022+DOM only), but this file needs node:fs/node:path/
// process to read the stylesheet as text. Scoped to this file alone rather
// than adding @types/node as a real dependency or touching the shared
// tsconfig for every other file under tests/ (same convention as
// _generate-fuzz-vectors.test.ts).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Regression coverage for fix-round-1 review findings on the vendored theme CSS
// (client-kit/rich-text/src/cms-rich.css): these are string assertions on the
// stylesheet itself, since the bugs are about which selector a rule is scoped
// to (inline vs. block wrapper, and UA-default margins on li/blockquote's
// first child) rather than about computed styles a jsdom test can observe.
const css = readFileSync(join(process.cwd(), "src/cms-rich.css"), "utf8");

describe("cms-rich.css", () => {
  it("scopes the block-flow spacing rule away from the inline wrapper", () => {
    // .cms-rich > * + * alone would also match RichWords' per-word inline-block
    // spans and inline <RichText> children, adding unwanted margin-top to every
    // word after the first in per-word animations.
    expect(css).toContain(".cms-rich:not(.cms-rich--inline) > * + *");
    // The bare (unscoped) selector must be gone — ":not(...)" always sits
    // directly after ".cms-rich" in the scoped form, so this substring check
    // can't accidentally match the fixed version.
    expect(css).not.toContain(".cms-rich > * + *");
  });

  it("keeps the li block-flow spacing rule (rich lists still need it)", () => {
    expect(css).toContain(".cms-rich li > * + *");
  });

  it("resets UA default margin-top on li's and blockquote's first child", () => {
    // normalize.ts always wraps li/blockquote content in <p> (or <ul>/<ol>);
    // without this, plain-CSS sites (no Tailwind preflight) keep the browser's
    // default p/blockquote margin-top, which collapses through li and adds
    // unwanted space contrary to spec §7's "a site that sets nothing still
    // looks correct" promise.
    expect(css).toContain(".cms-rich li > :first-child, .cms-rich blockquote > :first-child { margin-top: 0; }");
  });

  it("removes the UA default horizontal inset on blockquote", () => {
    expect(css).toMatch(/\.cms-rich blockquote\s*\{[^}]*margin-left:\s*0;/);
    expect(css).toMatch(/\.cms-rich blockquote\s*\{[^}]*margin-right:\s*0;/);
  });
});
