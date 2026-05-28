# Design Prompt Creator Agent — Design Spec

**Date:** 2026-05-21
**Branch:** `feat/lead-scraper-system`
**Author:** Stefan + Claude (Opus 4.7)
**Status:** Design — pending review

---

## 1. Problem

The previous attempt (see the now-superseded *Generate Design Prompt* spec) shipped a backend-driven, GitHub-Actions-worker version that turned out to be the wrong shape for Stefan's workflow. He wants:

- To trigger the generator **from Claude Code locally**, not from a button in the dashboard.
- The generator to **research the web** for popular websites in the lead's category and use real-world patterns to inform the prompt — not rely only on the playbook in the `lead-to-design-prompt` skill.
- The output to land in the existing `leads.design_prompt` column so he can review, hand-edit, then paste into [claude.ai/design](https://claude.ai/design) himself.
- The agent to **self-improve** — feedback he leaves after each run should shape future runs.
- Research findings to **persist and compound** — a popular cafe website the agent visited last week should inform decisions on this week's cafe lead without re-fetching.

The previous backend/worker/dashboard plumbing is being torn down (§9 covers the revert). The two pieces worth keeping are the `lead-to-design-prompt` skill itself and the `leads.design_prompt` TEXT column.

## 2. Goal

Ship a new local agent at `agents/Design Prompt creator/` plus a triggering skill at `.claude/skills/design-prompt-creator/SKILL.md` that:

- Reads a lead row from Supabase by id (via the Supabase MCP, not the backend).
- Parses Stefan's trigger prompt for mode hints (`force fresh research`, `skip research`, `reuse structure from lead <X>`, `dry-run`, free-form style hints).
- Consumes any pending feedback files into `LEARNINGS.md` before generating, so corrections compound.
- Reads the per-category research file (`research/<category>.md`), decides whether fresh research is needed, and runs WebSearch + WebFetch in bounded fashion when it is.
- Invokes the existing `lead-to-design-prompt` skill with the lead JSON enriched with research findings + relevant LEARNINGS as additional context.
- Writes the resulting XML to `leads.design_prompt` wrapped in `<pre><code>…</code></pre>` so the existing `DesignPromptSection` (TipTap, dangerouslySetInnerHTML) renders it as a code block.
- Auto-creates a blank feedback template at `feedback/pending/lead_<id>_<date>.md` so leaving useful feedback is friction-free.

**Non-goals (locked YAGNI):**

- No automated tests, no Python modules. The agent IS the markdown contract Claude follows.
- No backend integration. Supabase access is exclusively via `mcp__supabase__execute_sql`.
- No GitHub Actions, no scheduling, no remote runtime.
- No automatic "training" command — learning happens organically each run.
- No structured frontend UI for the agent. The existing `DesignPromptSection` (rich-text editor) is the review surface.
- No multi-lead batch mode for v1 (one lead per invocation).
- No per-lead research caching — only per-category (compound learning is the point).
- No DB audit table of runs / versions — the previous attempt's history table is being dropped.

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Stefan in Claude Code                                            │
│                                                                   │
│  "Run Design Prompt Creator for lead db28… [optional hints]"     │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
                ┌──────────────────────────────────┐
                │  .claude/skills/design-prompt-   │
                │  creator/SKILL.md                │
                │  (trigger + first-step rules)    │
                └────────────────┬─────────────────┘
                                 │ delegates to
                                 ▼
                ┌──────────────────────────────────┐
                │  agents/Design Prompt creator/   │
                │  AGENTS.md                       │
                │  (authoritative spec)            │
                └────────────────┬─────────────────┘
                                 │ phase pipeline (0 → 6)
   ┌─────────────────────────────┼─────────────────────────────┐
   │                             │                             │
   ▼                             ▼                             ▼
Phase 0/1                  Phase 2/3/4                   Phase 5/6
Parse + load lead         Consume feedback,             Generate via
                          read/update research          lead-to-design-
                                                        prompt skill,
                                                        write back
   │                             │                             │
   │   uses MCP                  │   reads/edits markdown      │   uses MCP + skill chain
   │                             │                             │
   ▼                             ▼                             ▼
mcp__supabase__              filesystem:                  Skill tool +
execute_sql                  feedback/, research/,        mcp__supabase__
(SELECT leads)               LEARNINGS.md                 execute_sql (UPDATE)
                                                          + WebSearch/WebFetch
                                                          (Phase 4 only)
```

No always-on infrastructure. The agent runs only when Stefan triggers it from Claude Code.

## 4. Folder layout

```
agents/Design Prompt creator/
├── AGENTS.md                      # authoritative spec
├── LEARNINGS.md                   # auto-updated lessons (distilled feedback)
├── README.md                      # 1-page quick reference
├── phases/
│   ├── 0-parse-intent.md
│   ├── 1-load-lead.md
│   ├── 2-consume-feedback.md
│   ├── 3-check-research.md
│   ├── 4-research.md
│   ├── 5-generate.md
│   └── 6-writeback.md
├── research/
│   ├── restaurant.md              # auto-grown reference library
│   ├── cafe.md
│   ├── salon.md
│   ├── venue.md
│   ├── retail.md
│   └── service.md
├── feedback/
│   ├── pending/                   # Stefan drops notes here per lead
│   ├── archive/                   # auto-moved after Phase 2 consumes them
│   └── README.md                  # template + workflow notes
└── runs/                          # fallback save target if Supabase write fails

.claude/skills/design-prompt-creator/
└── SKILL.md                       # trigger pattern + first steps
```

**No Python modules** for v1. If we later extract deterministic helpers (e.g., a research-staleness checker), they live alongside the markdown — not as a replacement for it.

## 5. Trigger and intent parsing (Phase 0)

### 5.1 Skill trigger

The skill description (in `SKILL.md` frontmatter) triggers on:

> "Run Design Prompt Creator for lead `<lead_id>` [hints…]"

Close paraphrases match too: *"Generate design prompt for lead X"*, *"Create design brief for X"*, *"Design Prompt Creator on X"*.

If the trigger fires but `lead_id` is missing or unrecognisable, the agent asks once and halts if no answer.

### 5.2 Mode hints

Phase 0 parses Stefan's prompt for these tokens and flags them on the run context:

| Token | Effect |
|---|---|
| `force fresh research` | Phase 3 always says "research needed", Phase 4 always runs |
| `skip research` / `cache only` | Phase 4 unconditionally skipped |
| `dry-run` | Phase 6 prints output to chat, **no** Supabase write, **no** feedback template created |
| `verbose` | Each phase echoes a 1-line summary of what it found / decided |
| `reuse structure from lead <X>` | Phase 5 fetches lead X's existing `design_prompt`, passes it as an extra reference to the skill |
| `style hint: <free text>` | Free-form aesthetic hint, threaded into the skill's invocation context |

Multiple tokens can appear; unrecognised tokens are passed through as free-form context (with a warning if they look like they were meant as flags).

### 5.3 Clarifying-question rules

The agent must ask once and wait when:

| Situation | Question |
|---|---|
| `lead_id` missing or ambiguous | "Which lead? Paste id." |
| Lead has no `business_name` or no `category` | "Lead X is missing `category` — guess from description, or halt?" |
| `force fresh research` requested but cache already has ≥10 brands documented for the category | "Cache for `<category>` already has 12 brands. Research more anyway, or use existing?" |
| Stefan's hint contradicts an anti-pattern from `lead-to-design-prompt` (e.g., purple gradient, banned font) | "That choice is on the anti-slop ban list. Propose `<alternative A/B>` in the same mood — OK?" |
| `reuse structure from lead <X>` but X has no `design_prompt` set | "Lead X has no `design_prompt`. Pick a different reference or proceed without?" |
| Phase 5 output has no fenced ` ```xml ` block | Show first 500 chars, ask retry / save-as-is / abort |

The agent never assumes when there's a genuine ambiguity. It does *not* ask for confirmation on routine choices (which archetype to pick, which sites to research) — those are its job.

## 6. Pipeline (phases 0 → 6)

Each phase has its own markdown doc in `phases/`. Claude reads only the active phase doc on entry; previous phase docs are not kept in active context.

### Phase 0 — Parse intent

- Extract `lead_id` and mode flags from the trigger prompt (§5.2).
- If clarifying conditions hit (§5.3), ask and wait.
- Echo a one-line plan: *"Lead <id> · mode: <flags or default>. Phases 1–6 to follow."*

### Phase 1 — Load lead

- `mcp__supabase__execute_sql` SELECT * FROM leads WHERE id = '<lead_id>'.
- Normalise: strip placeholders (`"Not found"`, `"N/A"`, `"-"`), expand country ISO codes, drop the map embed if lat/lng is null.
- **Strip the `<pre><code>…</code></pre>` wrapper** from `lead.design_prompt` if present (it's the agent's previous output, used as iteration context by the skill — the skill expects raw text, not wrapped HTML). If it's plain text already (e.g., Stefan hand-edited), pass through unchanged.
- Classify into one of the 6 buckets used by the `lead-to-design-prompt` skill (restaurant / cafe / salon / venue / retail / service).
- Project to the skill-input whitelist (preserved in §12 below for the implementation plan).
- If lead missing required fields → §5.3 clarifying question.

### Phase 2 — Consume feedback

- Glob `feedback/pending/*.md`.
- For each file: read it, identify the *generalisable* lesson, then:
  - If a similar lesson exists in `LEARNINGS.md`, merge or strengthen (don't duplicate).
  - If it contradicts an existing lesson, replace and note the date (newer wins).
  - If the file was marked "discard if not generalisable" or is purely lead-specific, drop the lesson but still archive the file.
- Move consumed files to `feedback/archive/<YYYY-MM>/<lead_id>.md`.
- Print: *"Consumed N feedback files, updated LEARNINGS by M entries."*

### Phase 3 — Check research cache

Read `research/<category>.md`. Decide whether fresh research is needed using three signals:

1. **Staleness:** `last_refreshed` more than 60 days ago.
2. **Coverage:** fewer than 5 reference brands documented.
3. **Archetype gap:** the lead's specific archetype (e.g., fine dining vs casual bistro) is not represented in documented brands.

If `force fresh research` flag is set → research needed (skip the signals).
If `skip research` / `cache only` flag is set → research skipped (skip the signals).
Otherwise: research needed if **any** of the 3 signals trip.

Echo: *"Research <needed | sufficient | overridden by flag>. Signals: staleness=<bool>, coverage=<n>/5, archetype `<X>` <present|missing>."*

### Phase 4 — Research (conditional)

Only runs if Phase 3 said yes.

- At most **4 WebSearch queries** (e.g., *"popular minimalist Italian restaurant websites 2026"*, *"award-winning <category> design"*).
- At most **4 WebFetch calls**, one per chosen site. Each capped at 100 KB.
- For each fetched site, extract: typography pairing, palette, layout patterns, hero treatment, structural choices, anything notable.
- Append entries to `research/<category>.md` under "Reference brands".
- If ≥5 brands of one archetype now exist, regenerate the "Common patterns observed" summary at the bottom of the file.
- Update `last_refreshed: <today>` at the top of the file.

Failure modes:
- WebSearch returns nothing useful → skip research, proceed with existing knowledge.
- A specific WebFetch fails → skip that URL, try next.
- All 4 fetches fail → proceed without fresh research, warn in chat.

### Phase 5 — Generate

Invoke the `lead-to-design-prompt` skill with:

```
Generate a design prompt for this lead:

```json
<whitelisted lead JSON>
```

<additional_context>
## Research insights for this category
<copy "Common patterns observed" block + the 3-5 most relevant brand summaries from research/<category>.md>

## Lessons from prior runs
<copy relevant LEARNINGS.md entries — General section + this category's section>

## Style hints from the trigger
<free-form text Stefan passed via `style hint: ...`>

## Reference prompt to follow structure from
<only if `reuse structure from lead <X>` was set; fetch lead X's design_prompt, strip the <pre><code> wrapper if present, copy raw XML here>
</additional_context>
```

The skill produces the same XML-tagged Markdown blob it does today. The agent extracts the first fenced ` ```xml ` block from the skill's output.

If extraction fails → §5.3 clarifying question.

### Phase 6 — Write back

- If `dry-run` flag is set: print the XML + the would-be feedback path to chat. No DB write, no feedback file. Stop.
- Otherwise:
  - Wrap the XML: `<pre><code>` + raw XML + `</code></pre>`. This renders cleanly in the existing `DesignPromptSection` (which uses `dangerouslySetInnerHTML`).
  - `mcp__supabase__execute_sql`: `UPDATE leads SET design_prompt = '<wrapped>' WHERE id = '<lead_id>'`.
  - Create `feedback/pending/lead_<id>_<YYYY-MM-DD>.md` from the template (§7.3).
  - Print: *"✓ Written to leads.design_prompt (length: N chars). Feedback template: `feedback/pending/lead_<id>_<date>.md`."*
- If the UPDATE fails: save the XML to `runs/<lead_id>_<datestamp>.xml`, report the path, do not lose work.

## 7. File formats

### 7.1 `research/<category>.md`

```markdown
# Research — Restaurant

**Last refreshed:** 2026-05-21

## Reference brands

### Le Bernardin · https://www.le-bernardin.com/
- **Type:** Fine dining
- **Typography:** Custom serif display + thin sans body
- **Palette:** Cream + deep teal accent, sparse imagery
- **Layout:** Asymmetric hero, generous whitespace, low-density nav
- **Notable:** Menu as image (not HTML), no online ordering
- **Researched:** 2026-05-21

### Osteria Francescana · https://...
…

## Common patterns observed

- Fine dining: custom serif display ~always
- Casual bistros: editorial-magazine layouts trending in 2026
- Pizzerias: lean into warm photography, less typography focus
```

The "Common patterns observed" block is regenerated whenever Phase 4 adds new brands and at least 5 brands exist for one archetype within the file.

### 7.2 `LEARNINGS.md`

```markdown
# Learnings — Design Prompt Creator

## General

- (2026-05-22) Stefan prefers darker colour values — bump primary
  saturation toward forest/burgundy rather than mid-tones.

## Category: restaurant

- (2026-05-23) For SMB Italian restaurants, lean editorial-magazine
  over warm-photographic — feedback on lead db28… said photographic
  default felt too generic.

## Category: cafe

- (2026-05-24) Skip the obvious "third-wave coffee" tropes (kraft
  paper, hand-lettering) unless the brief explicitly requests rustic.
```

Each entry: short, sourced (date), generalisable. Per-lead specifics are dropped during distillation (§6 Phase 2).

### 7.3 `feedback/pending/lead_<id>_<date>.md` template (auto-created by Phase 6)

```markdown
# Feedback — Lead <id> (<business_name>)

Generated: <date>

## What I changed before sending to Claude Design

- (e.g., "Replaced the suggested Cormorant + Inter pair with Söhne + EB Garamond")

## Why

- (e.g., "Inter is on our anti-slop list; Söhne fits the brief better")

## Generalisable lesson

- (e.g., "Default away from Inter for boutique businesses even if 'modern'")

## (optional) Discard if not generalisable

- Leave this section if the change was purely lead-specific
```

## 8. Error handling and limits

Per-phase failure behavior is documented in §6. Global limits:

- WebSearch: **max 4** queries per run.
- WebFetch: **max 4** URLs per run, each capped at 100 KB.
- Token budget target: **30K–80K input**. Hard cap: 150K — if approaching, skip the "Common patterns" regeneration in Phase 4 and only append new brand entries.
- Wall-clock target: **under 5 minutes** per run.
- Supabase: a single SELECT (Phase 1) and a single UPDATE (Phase 6). No bulk writes.

## 9. Cleanup of Tasks 1–12 (full revert)

### 9.1 Supabase

New migration `backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql`:

```sql
DROP TABLE IF EXISTS lead_design_prompt_generations;
DROP TYPE IF EXISTS lead_design_prompt_generation_status;
```

Apply via `mcp__supabase__apply_migration`.

### 9.2 Backend — delete

- `backend/auth_service/services/design_prompt_dispatch.py`
- `backend/auth_service/tests/test_design_prompt_dispatch.py`
- `backend/auth_service/tests/test_design_prompt_schemas.py`
- `backend/auth_service/tests/test_admin_design_prompt_router.py`
- `backend/migrations/2026_05_21_lead_design_prompt_generations.sql`

### 9.3 Backend — revert (additive-only restoration to pre-Task-2/4/5/6 state)

- `backend/auth_service/models/schemas.py` — drop `DesignPromptGenerationStatus`, `DesignPromptGenerationOut`, `DesignPromptGenerationsListOut`, `DesignPromptGenerationPatch`. Drop the `Any` import addition.
- `backend/auth_service/routers/admin_leads.py` — drop the schema/dispatch imports, the whitelist helper, and the three new endpoints (POST/GET/PATCH).

### 9.4 Worker + workflow — delete

- `scripts/generate_design_prompt.py`
- `scripts/tests/__init__.py` and `scripts/tests/test_generate_design_prompt.py`
- `.github/workflows/generate-design-prompt.yml`
- (If `scripts/` is empty after this, leave the directory — it's a generic top-level location that other future work may use.)

### 9.5 Frontend — delete

- `frontend/src/components/admin/leads/hooks/useDesignPromptGenerations.ts`
- `frontend/src/components/admin/leads/hooks/__tests__/useDesignPromptGenerations.test.ts`
- `frontend/src/components/admin/leads/sections/GeneratedDesignPromptSection.tsx`
- `frontend/src/components/admin/leads/sections/__tests__/GeneratedDesignPromptSection.test.tsx`

### 9.6 Frontend — revert

- `frontend/src/components/admin/leads/types.ts` — drop `DesignPromptGenerationStatus`, `DesignPromptGeneration`, `DesignPromptGenerationsResponse`.
- `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` — drop the import + the `<GeneratedDesignPromptSection leadId={lead.id} />` JSX line.

### 9.7 Spec + plan docs — delete

- `docs/superpowers/specs/2026-05-21-generate-design-prompt-design.md`
- `docs/superpowers/plans/2026-05-21-generate-design-prompt.md`

### 9.8 Stays untouched

- `leads.design_prompt` TEXT column (this agent writes to it).
- `DesignPromptSection.tsx` (becomes the review/edit surface for the agent's output).
- `.claude/skills/lead-to-design-prompt/` (this agent invokes it).
- All other dashboard work (lead editing sections, conversions, scraper, etc.).

## 10. Self-improvement loop

```
Stefan triggers run 1
  → Phase 6 writes leads.design_prompt + feedback/pending/lead_X_<date>.md
Stefan reviews leads.design_prompt in the dashboard, edits as needed, pastes into Claude Design
Stefan opens feedback/pending/lead_X_<date>.md and jots down lessons
Stefan triggers run 2 (any lead)
  → Phase 2 reads ALL pending feedback (incl. lead_X)
  → Phase 2 distills into LEARNINGS.md, archives consumed files
  → Phases 3-6 use the updated LEARNINGS + research/ as additional_context
```

`LEARNINGS.md` grows with distilled lessons. `research/<category>.md` grows with documented brands and observed patterns. **No special "training" command** — the agent learns whenever it runs.

If Stefan does not leave feedback for a lead, that's fine — `feedback/pending/` simply stays empty for that lead and Phase 2 finds nothing to consume next run.

## 11. Implementation files (preview for the implementation plan)

**New (created):**

- `agents/Design Prompt creator/AGENTS.md`
- `agents/Design Prompt creator/LEARNINGS.md` (empty skeleton)
- `agents/Design Prompt creator/README.md`
- `agents/Design Prompt creator/phases/0-parse-intent.md`
- `agents/Design Prompt creator/phases/1-load-lead.md`
- `agents/Design Prompt creator/phases/2-consume-feedback.md`
- `agents/Design Prompt creator/phases/3-check-research.md`
- `agents/Design Prompt creator/phases/4-research.md`
- `agents/Design Prompt creator/phases/5-generate.md`
- `agents/Design Prompt creator/phases/6-writeback.md`
- `agents/Design Prompt creator/research/{restaurant,cafe,salon,venue,retail,service}.md` (empty skeletons)
- `agents/Design Prompt creator/feedback/README.md`
- `agents/Design Prompt creator/feedback/pending/.gitkeep`
- `agents/Design Prompt creator/feedback/archive/.gitkeep`
- `agents/Design Prompt creator/runs/.gitkeep`
- `.claude/skills/design-prompt-creator/SKILL.md`
- `backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql`

**Deleted / reverted:** see §9.

**Stays untouched:** see §9.8.

## 12. Skill input whitelist (carried over from the previous attempt)

The `lead-to-design-prompt` skill consumes these lead fields. Phase 1 projects the lead row to this whitelist before passing to Phase 5:

```
business_name, category, description, about, design_prompt,
country, region, city, address, postal_code, lat, lng,
phone, email, website_url, facebook_url, instagram_url,
menu_url, web_presence, source_url,
rating, review_count, reviews,
opening_hours, extra, notes
```

Plus `photo_urls` injected into `extra.photo_urls`.

> **Note:** the lead's existing `design_prompt` field is the *prior generation* from this very agent (or the empty initial state on first run). On a re-run, Phase 1 strips the `<pre><code>…</code></pre>` wrapper so the skill receives the raw prior text — that's how iterative refinement works. The skill uses this field as `<user_override priority="highest">`.

## 13. Open questions

- **Research file initial seeding** — should we pre-seed each `research/<category>.md` with the reference brands already listed in `.claude/skills/lead-to-design-prompt/references/reference-brands-by-category.md`, or start them empty and let the agent populate organically? Spec assumes **empty start** — simpler, and the skill's reference-brands file still informs the skill's own output.
- **`feedback/archive/` rotation** — files there grow forever. No rotation in v1. If it gets large, add a yearly summarisation pass later.
- **MCP project_id** — the agent needs to know which Supabase project id to target. Encode it in `AGENTS.md` as a constant (`xeluydwpgiddbamysgyu` per the `Job - Agent`/`CMS`/`fastApi - demo` project list — `CMS` is the live one Stefan uses). Confirm in implementation.

## 14. Testing posture

No unit tests for v1. The agent IS a markdown contract — there are no Python helpers to test. Verification is manual:

1. Run on a known lead with no feedback yet → confirm sensible XML lands in `leads.design_prompt`.
2. Write feedback for that lead in `feedback/pending/`.
3. Run on a different lead → confirm `LEARNINGS.md` was updated AND the new prompt reflects the lesson.
4. Run again with `dry-run` flag → confirm nothing is written to DB or feedback queue.
5. Run again with `force fresh research` → confirm WebSearch fires and new brands land in `research/<category>.md`.

If we later extract logic into Python (e.g., a research staleness checker), we add `pytest` files at that point — not before.

## 15. Out of scope (revisit later)

- Token cost / usage telemetry per run.
- A Slack notification when a run completes.
- Bulk mode (run for N leads in one invocation).
- Switching between Sonnet 4.6, Opus 4.7, Haiku per run.
- Per-city / per-region competitor research (would be the "C" tier from brainstorming Q3 — adds a second tier on top of per-category).
- A frontend "Generate" button. The agent is intentionally CLI-driven (Claude Code) for v1.
- Automatic research refresh on a schedule.
