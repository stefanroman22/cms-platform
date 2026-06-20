#!/usr/bin/env node
/**
 * Translate messages/en.json → nl.json + ro.json with DeepL.
 * - Incremental: only (re)translates leaf strings whose English source changed
 *   since the last run (tracked in messages/.translation-cache.json), so manual
 *   edits to nl/ro are preserved.
 * - Protects ICU placeholders ({name}) and the brand "Roman Technologies" from
 *   translation via DeepL XML tag handling.
 *
 * Usage:  DEEPL_API_KEY=xxxx node scripts/translate-i18n.mjs
 */
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MESSAGES = path.join(__dirname, "..", "messages");
const TARGETS = { nl: "NL", ro: "RO" };
const KEY = process.env.DEEPL_API_KEY;
if (!KEY) {
  console.error("DEEPL_API_KEY is not set. Aborting.");
  process.exit(1);
}
const ENDPOINT = KEY.endsWith(":fx")
  ? "https://api-free.deepl.com/v2/translate"
  : "https://api.deepl.com/v2/translate";

const DO_NOT_TRANSLATE = ["Roman Technologies"];

const hash = (s) => createHash("sha1").update(s).digest("hex");
const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);

// Flatten nested object/array into { "a.b.0": "leaf string" } (strings only).
function flatten(node, prefix = "", out = {}) {
  if (typeof node === "string") {
    out[prefix] = node;
  } else if (Array.isArray(node)) {
    node.forEach((v, i) => flatten(v, prefix ? `${prefix}.${i}` : `${i}`, out));
  } else if (isObj(node)) {
    for (const k of Object.keys(node)) flatten(node[k], prefix ? `${prefix}.${k}` : k, out);
  }
  return out;
}

function setPath(root, dottedKey, value) {
  const parts = dottedKey.split(".");
  let cur = root;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i];
    const nextIsIndex = /^\d+$/.test(parts[i + 1]);
    if (cur[k] === undefined) cur[k] = nextIsIndex ? [] : {};
    cur = cur[k];
  }
  cur[parts[parts.length - 1]] = value;
}

// XML escaping so raw "&", "<", ">" in the copy don't break tag_handling=xml.
const xmlEscape = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const xmlUnescape = (s) =>
  s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");

// Wrap ICU placeholders + brand terms in ignored <x> tags so DeepL leaves them
// verbatim. The human text is XML-escaped first ({ } are not XML-special, so ICU
// placeholders still match after escaping). Braces are matched in a BALANCED way
// so complex ICU args ({n, plural, one {…} other {…}}) are protected as one unit
// and DeepL can never break the plural/select syntax. (Words inside a plural stay
// English; localize those few by hand.)
function wrapBalancedBraces(t) {
  let out = "";
  let i = 0;
  while (i < t.length) {
    if (t[i] === "{") {
      let depth = 0;
      let j = i;
      for (; j < t.length; j++) {
        if (t[j] === "{") depth++;
        else if (t[j] === "}" && --depth === 0) {
          j++;
          break;
        }
      }
      out += `<x>${t.slice(i, j)}</x>`;
      i = j;
    } else {
      out += t[i++];
    }
  }
  return out;
}

function protect(text) {
  let t = wrapBalancedBraces(xmlEscape(text));
  for (const term of DO_NOT_TRANSLATE) {
    t = t.split(xmlEscape(term)).join(`<x>${term}</x>`);
  }
  return t;
}
function unprotect(text) {
  return xmlUnescape(text.replace(/<x>(.*?)<\/x>/g, "$1"));
}

async function deepl(texts, targetLang) {
  const body = new URLSearchParams();
  for (const t of texts) body.append("text", protect(t));
  body.append("source_lang", "EN");
  body.append("target_lang", targetLang);
  body.append("tag_handling", "xml");
  body.append("ignore_tags", "x");
  body.append("preserve_formatting", "1");

  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `DeepL-Auth-Key ${KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
  if (!res.ok) throw new Error(`DeepL ${res.status}: ${await res.text()}`);
  const json = await res.json();
  return json.translations.map((t) => unprotect(t.text));
}

async function main() {
  const en = JSON.parse(await readFile(path.join(MESSAGES, "en.json"), "utf8"));
  const cachePath = path.join(MESSAGES, ".translation-cache.json");
  let cache = {};
  try {
    cache = JSON.parse(await readFile(cachePath, "utf8"));
  } catch {
    cache = {};
  }

  const enFlat = flatten(en);

  for (const [locale, lang] of Object.entries(TARGETS)) {
    const outPath = path.join(MESSAGES, `${locale}.json`);
    let existing = {};
    try {
      existing = JSON.parse(await readFile(outPath, "utf8"));
    } catch {
      existing = {};
    }
    const existingFlat = flatten(existing);
    const result = {};
    cache[locale] = cache[locale] || {};

    // Decide which keys need (re)translation.
    const toTranslate = [];
    for (const [key, source] of Object.entries(enFlat)) {
      const h = hash(source);
      const unchanged = cache[locale][key] === h && existingFlat[key] !== undefined;
      if (unchanged) {
        setPath(result, key, existingFlat[key]); // keep prior (possibly human-edited) value
      } else {
        toTranslate.push({ key, source, h });
      }
    }

    // Translate in batches of 50 (DeepL allows up to 50 text params per call).
    for (let i = 0; i < toTranslate.length; i += 50) {
      const batch = toTranslate.slice(i, i + 50);
      const translated = await deepl(
        batch.map((b) => b.source),
        lang
      );
      batch.forEach((b, j) => {
        setPath(result, b.key, translated[j]);
        cache[locale][b.key] = b.h;
      });
      console.log(`[${locale}] ${Math.min(i + 50, toTranslate.length)}/${toTranslate.length}`);
    }

    await writeFile(outPath, JSON.stringify(result, null, 2) + "\n", "utf8");
    console.log(`[${locale}] wrote ${outPath} (${toTranslate.length} new/changed)`);
  }

  await writeFile(cachePath, JSON.stringify(cache, null, 2) + "\n", "utf8");
  console.log("Done. Review nl.json / ro.json before committing.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
