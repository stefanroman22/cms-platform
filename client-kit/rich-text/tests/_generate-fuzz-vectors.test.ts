// @ts-nocheck — this project has no @types/node (it's a browser-facing kit;
// tsconfig's lib is ES2022+DOM only), but this one generator script is a
// Node-only dev tool that needs node:fs/node:path/process/__dirname. Scoped
// to this file alone rather than adding @types/node as a real dependency or
// touching the shared tsconfig for every other file under tests/.
//
// Generator, not a real test: regenerates fixtures/fuzz-vectors.json, a
// seeded random tag-soup corpus run through the kit's own
// parse()+normalize()+serialize() pipeline, for the backend's differential
// fuzz test (backend/auth_service/tests/test_rich_text_fuzz_parity.py) to
// replay against `canonicalize()` and assert equality.
//
// Committed here (not run ad hoc) so the corpus is reproducible and
// reviewable in a diff. It intentionally does nothing on a normal
// `npx vitest run` — it only touches disk when GENERATE_FUZZ_VECTORS=1 is
// set, so the committed fixture never silently drifts from what's checked
// in. To regenerate after changing FRAGMENTS/COUNT/SEED below:
//
//   GENERATE_FUZZ_VECTORS=1 npx vitest run tests/_generate-fuzz-vectors.test.ts
//
// SEED is fixed and documented (not derived from Date.now() or similar) so
// two regenerations with unchanged FRAGMENTS/COUNT produce byte-identical
// output — this is what "seeded" means for the differential test's purpose:
// a stable, committed, re-derivable corpus, not fresh randomness per run.
import { describe, expect, it } from "vitest";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse } from "../src/parse";
import { normalizeInline, normalizeRich } from "../src/normalize";
import { serialize } from "../src/serialize";

const SEED = 20260927;
const COUNT = 2000;

// mulberry32: a tiny deterministic PRNG (same output for the same seed on
// any JS engine, unlike Math.random()).
function mulberry32(seed: number): () => number {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Fragments exercise: every RICH_TAGS member and every SYNONYMS source tag,
// unknown/DROP_WITH_CONTENT tags (incl. script/style raw-text), attributes
// with double/single/unquoted/missing values, self-closing tags, comments
// (terminated and unterminated), <!DOCTYPE>, <?pi?>, <![CDATA[...]]> and a
// bogus <![x> marked section, bare unterminated tag-opens, stray `<`/`>`,
// mismatched/unbalanced close tags, nesting, and entities — both the safe
// set (amp/lt/gt/quot/apos/nbsp, which the kit and backend agree on) and a
// few outside it (e.g. &copy;, &hearts;) so the corpus also covers the
// documented, accepted kit/backend entity-table gap; the Python side skips
// strict equality only for cases containing one of those.
const FRAGMENTS: string[] = [
  "hello",
  "world",
  "  spaced  ",
  "\n\t line \n",
  "😀",
  "café",
  "<p>x</p>",
  "<p>a</p><p>b</p>",
  "<div>d</div>",
  "<span>s</span>",
  "<strong>b</strong>",
  "<b>b2</b>",
  "<em>i</em>",
  "<i>i2</i>",
  "<u>u</u>",
  "<s>s2</s>",
  "<strike>strike</strike>",
  "<del>del</del>",
  "<ins>ins</ins>",
  "<h1>H1</h1>",
  "<h2>H2</h2>",
  "<h3>H3</h3>",
  "<h4>H4</h4>",
  "<h5>H5</h5>",
  "<h6>H6</h6>",
  "<ul><li>a</li><li>b</li></ul>",
  "<ol><li>a</li></ol>",
  "<li>bare</li>",
  "<blockquote>q</blockquote>",
  "<hr>",
  "<hr/>",
  "<br>",
  "<br/>",
  '<a href="https://x.ro">l</a>',
  "<a href='https://y.ro'>l2</a>",
  "<a href=https://z.ro>l3</a>",
  '<a href="javascript:alert(1)">bad</a>',
  '<a href="//evil.com">rel</a>',
  '<a href="/local">loc</a>',
  '<a href="#top">hash</a>',
  '<a href="mailto:a@b.ro">mail</a>',
  '<a>nolink</a>',
  '<a href="a>b">quotegt</a>',
  "<abbr>unknown</abbr>",
  "<img src=x onerror=1>",
  "<script>alert(1)</script>",
  "<style>p{color:red}</style>",
  "<iframe>x</iframe>",
  "<svg><text>t</text></svg>",
  "<template>t</template>",
  "<noscript>n</noscript>",
  "<textarea>t</textarea>",
  "<select><option>o</option></select>",
  "<button>b</button>",
  "<canvas>c</canvas>",
  "<video>v</video>",
  "<audio>a</audio>",
  "<picture>p</picture>",
  "<math>m</math>",
  "<object>o</object>",
  "<!-- a comment -->",
  "<!-- unterminated",
  "<!--",
  "<!-->",
  "<!DOCTYPE html>",
  "<!doctype html>",
  "<?xml version=\"1.0\"?>",
  "<?php x ?>",
  "<![CDATA[x]]>",
  "<![CDATA[<script>x</script>]]>",
  "<![x>",
  "<![if !IE]>",
  "<![endif]>",
  "<b",
  "<a",
  "</b",
  "<a a",
  "< b",
  "a < b",
  "<>",
  "</>",
  "<3",
  "<b>unterminated inner<i>",
  "</strong>",
  "</div><div>",
  "<p><strong>nested</p></strong>",
  "&amp;",
  "&lt;",
  "&gt;",
  "&quot;",
  "&apos;",
  "&nbsp;",
  "&copy;",
  "&hearts;",
  "&#65;",
  "&#x41;",
  "&notanentity",
  "Tom & Jerry",
  '"quoted"',
  "'single'",
  " ",
  "﻿",
];

function pick(rnd: () => number, arr: string[]): string {
  return arr[Math.floor(rnd() * arr.length)]!;
}

function genCase(rnd: () => number): string {
  const n = 1 + Math.floor(rnd() * 8);
  let s = "";
  for (let i = 0; i < n; i++) s += pick(rnd, FRAGMENTS);
  return s;
}

describe("generate fuzz vectors (no-op unless GENERATE_FUZZ_VECTORS=1)", () => {
  it("writes fixtures/fuzz-vectors.json", () => {
    if (!process.env.GENERATE_FUZZ_VECTORS) {
      expect(true).toBe(true);
      return;
    }
    const rnd = mulberry32(SEED);
    const canonical = (input: string, fmt: "inline" | "rich") => {
      const root = parse(input);
      return serialize(
        fmt === "inline" ? normalizeInline(root.children) : normalizeRich(root.children),
      );
    };
    const vectors: { i: number; fmt: "inline" | "rich"; input: string; expected: string }[] = [];
    for (let i = 0; i < COUNT; i++) {
      const input = genCase(rnd);
      const fmt: "inline" | "rich" = i % 2 === 0 ? "rich" : "inline";
      const expected = canonical(input, fmt);
      vectors.push({ i, fmt, input, expected });
    }
    writeFileSync(
      resolve(__dirname, "..", "fixtures", "fuzz-vectors.json"),
      JSON.stringify(vectors) + "\n",
    );
    expect(vectors.length).toBe(COUNT);
  });
});
