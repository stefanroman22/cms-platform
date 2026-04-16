#!/usr/bin/env node
/**
 * scripts/sync-cms-types.mjs
 *
 * Downloads the TypeScript type declarations for this project's CMS content
 * from the CMS `/content/{slug}/types` endpoint and writes them to cms.types.ts.
 *
 * Usage:
 *   node scripts/sync-cms-types.mjs
 *
 * Add to package.json:
 *   "cms:sync-types": "node scripts/sync-cms-types.mjs"
 *
 * Then run:
 *   npm run cms:sync-types
 */

import { writeFile, mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

// ── Read project slug ─────────────────────────────────────────────────────────
// Priority: CMS_PROJECT_SLUG env var → read from cms.config.json → error

let projectSlug = process.env.CMS_PROJECT_SLUG;
let endpoint = process.env.CMS_ENDPOINT ?? "https://cms.romantechnologies.com/content";

if (!projectSlug) {
    // Try to read from cms.config.json (simpler JSON alternative to the TS file)
    try {
        const { createRequire } = await import("node:module");
        const require = createRequire(import.meta.url);
        const config = require(join(ROOT, "cms.config.json"));
        projectSlug = config.projectSlug;
        endpoint = config.endpoint ?? endpoint;
    } catch {
        // cms.config.json not found — try parsing cms.config.ts for the slug
        try {
            const { readFile } = await import("node:fs/promises");
            const src = await readFile(join(ROOT, "cms.config.ts"), "utf-8");
            const match = src.match(/projectSlug:\s*["']([^"']+)["']/);
            const endpointMatch = src.match(/endpoint:\s*["']([^"']+)["']/);
            if (match) projectSlug = match[1];
            if (endpointMatch) endpoint = endpointMatch[1];
        } catch {
            /* ignore */
        }
    }
}

if (!projectSlug) {
    console.error(
        "❌  Could not determine project slug.\n" +
        "    Set CMS_PROJECT_SLUG env var, or create cms.config.json / cms.config.ts."
    );
    process.exit(1);
}

// ── Fetch types ───────────────────────────────────────────────────────────────

const typesUrl = `${endpoint}/${projectSlug}/types`;
console.log(`⬇  Fetching types from ${typesUrl} …`);

let body;
try {
    const res = await fetch(typesUrl);
    if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    body = await res.text();
} catch (err) {
    console.error(`❌  Fetch failed: ${err.message}`);
    process.exit(1);
}

// ── Write output ──────────────────────────────────────────────────────────────

const outPath = join(ROOT, "cms.types.ts");

await writeFile(outPath, body, "utf-8");

console.log(`✅  Types written to cms.types.ts`);
console.log(`    Import with: import type { CMSContent } from './cms.types'`);
