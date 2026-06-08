# Phase 1 — Load lead

**Goal:** Fetch the lead row, normalise it, classify into a category bucket, and prepare the skill-input payload.

**Inputs:** `lead_id` from Phase 0. Supabase MCP connection (project_id `xeluydwpgiddbamysgyu`).

## Steps

1. Call `mcp__supabase__execute_sql`:

   ```sql
   SELECT * FROM leads WHERE id = '<lead_id>';
   ```

   If the result is empty → halt + report: *"Lead `<lead_id>` not found."*

2. Normalise the row:

   - Replace any field where the value is literally `"Not found"`, `"N/A"`, or `"-"` with `null`.
   - Expand 2-letter country ISO codes: `NL` → `Netherlands`, `BE` → `Belgium`, `DE` → `Germany`. Other codes: pass through unchanged.
   - If `lat` OR `lng` is null, set BOTH to null (the skill drops the map embed only when both are absent).
   - Pass `languages` (a `text[]` of canonical English language names, e.g. `["Dutch","English"]`) through as-is. An empty array means no explicit locales were set — the skill treats that as a single-language site.
   - **Strip `<pre><code>` wrapper from `design_prompt` if present:** look for `^\s*<pre><code>(.+?)</code></pre>\s*$` (DOTALL). If matched, replace with the captured content. If not matched, leave as-is.

3. Classify into one of the 6 category buckets (use `category` field; if ambiguous, infer from `description` + `extra.attributes`):

   - `restaurant` — restaurant, bistro, trattoria, brasserie, pizzeria, steakhouse, ramen, sushi, fine dining
   - `cafe` — cafe, coffee shop, bakery, patisserie, tea house, juice bar
   - `salon` — hair salon, barber, beauty salon, nail studio, spa, brow/lash studio
   - `venue` — wedding venue, event space, banquet hall, conference centre, ceremony location
   - `retail` — boutique, clothing store, gift shop, concept store, florist, jewellery
   - `service` — fallback for everything else

   If both `business_name` and `category` are empty/null → ask: *"Lead `<id>` has no `business_name` or `category`. Halt or guess from description?"*

4. Project the row to the **skill-input whitelist**:

   ```
   business_name, category, description, about, design_prompt,
   country, region, city, address, postal_code, lat, lng,
   phone, email, website_url, facebook_url, instagram_url,
   menu_url, web_presence, source_url,
   rating, review_count, reviews,
   opening_hours, extra, notes, languages
   ```

   Plus inject `photo_urls` into `extra.photo_urls` if `photo_urls` is non-empty:

   ```python
   extra = dict(lead.get("extra") or {})
   if lead.get("photo_urls"):
       extra["photo_urls"] = lead["photo_urls"]
   projected["extra"] = extra
   ```

   (This logic happens in Claude's working memory; nothing is written to disk in Phase 1.)

5. If `mode.verbose` is set, echo: *"Phase 1: lead `<business_name>` (category bucket: `<bucket>`)."*

## Outputs

- `lead` — the projected, normalised lead JSON
- `category_bucket` — one of the 6 strings above
- `previous_design_prompt` — the stripped raw text (or null), for use in Phase 5 if iterating

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Lead not found | "Lead `<id>` not found in Supabase." |
| Both name + category missing | "Lead `<id>` has no `business_name` or `category`. Halt or guess from description?" |
| Supabase MCP error | "Supabase MCP call failed: `<error>`. Check MCP connection and re-run." |

## Self-improvement hook

If category classification keeps mis-bucketing a class of leads (e.g., "bistro" → restaurant when Stefan would prefer it bucketed as cafe), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Bucket "<term>" as <bucket>. Triggered by: feedback on lead <id>.`
