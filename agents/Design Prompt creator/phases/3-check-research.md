# Phase 3 — Check research cache

**Goal:** Decide whether Phase 4 needs to run by checking the per-category research file against three freshness signals.

**Inputs:** `category_bucket` from Phase 1. Mode flags from Phase 0.

## Steps

1. If `mode.skip_research` is set → set `research_needed = false`, echo *"Phase 3: research skipped (flag)."*  Skip to Phase 4 (which becomes a no-op).

2. If `mode.force_research` is set:
   - Read `research/<bucket>.md` and count brand entries (count `### ` headings under `## Reference brands`).
   - If count ≥ 10 (i.e., `RESEARCH_FORCE_ASK_THRESHOLD`) → ask: *"Cache for `<bucket>` already has N brands. Research more anyway, or use existing?"* If answer is "use existing", set `research_needed = false`. Otherwise `research_needed = true`.
   - If count < 10, set `research_needed = true` directly.

3. Otherwise (default mode): check three signals:

   a. **Staleness:** read `Last refreshed: <date>` from line 3 of `research/<bucket>.md`. If `(never)` → `stale = true`. If a real date older than `RESEARCH_STALENESS_DAYS = 60` days ago → `stale = true`. Else `stale = false`.

   b. **Coverage:** count `### ` brand entries under `## Reference brands`. If count < `RESEARCH_MIN_BRANDS_PER_CATEGORY = 5` → `under_covered = true`. Else `false`.

   c. **Archetype gap:** identify the lead's archetype from `category` + `description` + `extra.attributes`. Examples:
      - Restaurant: fine dining / casual / pizzeria / bistro / ethnic
      - Cafe: third-wave coffee / bakery / brunch / tea
      - Salon: hair / nails / spa / beauty
      - Venue: wedding / corporate / banquet
      - Retail: boutique / florist / gift / concept
      - Service: consulting / agency / trades / fitness

      Scan the brand entries' `**Type:**` field for a matching archetype label. If none of the brand entries match, `archetype_gap = true`.

   Set `research_needed = stale OR under_covered OR archetype_gap`.

4. Echo one line:

   ```
   Phase 3: research <needed | sufficient | overridden>. signals=stale:<bool>,coverage:<n>/5,archetype:<present|missing>.
   ```

## Outputs

- `research_needed` (boolean)
- Brand count, archetype, freshness flags — pass-through to Phase 4 so it doesn't re-read the file

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `research/<bucket>.md` doesn't exist (shouldn't happen — Task 6 seeds them) | Create from skeleton (Task 6 template), then proceed as if `(never)` refreshed. |

## Self-improvement hook

If Phase 3 keeps saying "sufficient" but Stefan repeatedly forces fresh research on the same category, append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Lower staleness threshold for `<bucket>` to 30 days. Triggered by: 3+ runs forced research after 30-50 day gaps.`
