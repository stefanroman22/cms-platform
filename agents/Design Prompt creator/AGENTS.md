# Design Prompt Creator Agent

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/design-prompt-creator/SKILL.md`](../../.claude/skills/design-prompt-creator/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

> "Run Design Prompt Creator for lead `<lead_id>` [optional hints]"

Close paraphrases also match: *"Generate design prompt for lead X"*, *"Create design brief for X"*. The skill at `.claude/skills/design-prompt-creator/SKILL.md` enforces the trigger pattern.

Local-only. No remote triggering (no GitHub Actions, no cron). Stefan invokes from Claude Code in this repo.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|---|---|---|
| 0 | Parse intent | [phases/0-parse-intent.md](./phases/0-parse-intent.md) | Extract `lead_id` + mode flags from the trigger |
| 1 | Load lead | [phases/1-load-lead.md](./phases/1-load-lead.md) | Fetch + normalise + classify the lead |
| 2 | Consume feedback | [phases/2-consume-feedback.md](./phases/2-consume-feedback.md) | Distill `feedback/pending/*.md` into `LEARNINGS.md` |
| 3 | Check research | [phases/3-check-research.md](./phases/3-check-research.md) | Decide whether fresh research is needed |
| 4 | Research (conditional) | [phases/4-research.md](./phases/4-research.md) | WebSearch + WebFetch up to 4 sites, append to `research/<category>.md` |
| 5 | Generate | [phases/5-generate.md](./phases/5-generate.md) | Invoke `lead-to-design-prompt` skill with enriched context |
| 6 | Write back | [phases/6-writeback.md](./phases/6-writeback.md) | UPDATE `leads.design_prompt`, create feedback template |

## Constants

| Name | Value | Used by |
|---|---|---|
| `SUPABASE_PROJECT_ID` | `xeluydwpgiddbamysgyu` | Phases 1, 6 (every `mcp__supabase__execute_sql` call passes this) |
| `MAX_WEBSEARCH_QUERIES_PER_RUN` | 4 | Phase 4 |
| `MAX_WEBFETCH_URLS_PER_RUN` | 4 | Phase 4 |
| `WEBFETCH_BYTE_CAP` | 100 KB per URL | Phase 4 |
| `RESEARCH_STALENESS_DAYS` | 60 | Phase 3 |
| `RESEARCH_MIN_BRANDS_PER_CATEGORY` | 5 | Phase 3 |
| `RESEARCH_FORCE_ASK_THRESHOLD` | 10 brands | Phase 0 clarifying-question rule |

## Mode flags (parsed by Phase 0)

| Token in trigger | Effect |
|---|---|
| `force fresh research` | Phase 3 always says "research needed"; Phase 4 always runs |
| `skip research` / `cache only` | Phase 4 unconditionally skipped |
| `dry-run` | Phase 6 prints output, NO Supabase write, NO feedback template |
| `verbose` | Each phase echoes a 1-line summary of what it found |
| `reuse structure from lead <X>` | Phase 5 fetches lead X's `design_prompt` (strips wrapper) as extra reference |
| `style hint: <free text>` | Free-form aesthetic hint, threaded into Phase 5 context |

## Clarifying-question rules

The agent asks ONCE and waits when:

| Situation | Question |
|---|---|
| `lead_id` missing or ambiguous | "Which lead? Paste id." |
| Lead has no `business_name` or `category` | "Lead X is missing `category` — guess from description, or halt?" |
| `force fresh research` BUT cache already has ≥10 brands | "Cache for `<category>` already has N brands. Research more anyway, or use existing?" |
| Stefan's hint contradicts an anti-pattern (e.g., purple gradient) | "That choice is on the anti-slop ban list. Propose `<alternative>` in the same mood — OK?" |
| `reuse structure from lead <X>` but X has no `design_prompt` set | "Lead X has no `design_prompt`. Pick a different reference or proceed without?" |
| Phase 5 output has no fenced ` ```xml ` block | Show first 500 chars, ask retry / save-as-is / abort |

Routine choices (which archetype to pick, which sites to research, exact phrasing of copy seeds) are the agent's job — **never** ask Stefan about those.

## Tools the agent uses

- `Read`, `Edit`, `Write`, `Glob`, `Grep` — markdown + filesystem
- `WebSearch`, `WebFetch` — Phase 4 only
- `Skill` — to invoke `lead-to-design-prompt` (Phase 5)
- `mcp__supabase__execute_sql` — Phases 1 and 6, project_id `xeluydwpgiddbamysgyu`
- `Bash` — rare, mostly for `mv` archiving in Phase 2

The agent does **not** use the FastAPI backend. All Supabase access is direct via MCP.

## Self-improvement loop

Every run:
1. Phase 2 consumes pending feedback into `LEARNINGS.md`.
2. Phase 5 reads `LEARNINGS.md` + `research/<category>.md` and threads them as additional context into the `lead-to-design-prompt` skill call.
3. Phase 6 writes the result + creates a blank feedback template for this lead.

When Stefan reviews and adds notes to that template, the **next** run's Phase 2 picks them up — no manual "train the agent" command.

## Token rules

- Read phase docs lazily (one Read per phase, do not re-Read).
- Read LEARNINGS.md only after Phase 2 (Phase 2 itself reads + writes it).
- Read the relevant `research/<category>.md` once in Phase 3 (Phase 4 may re-edit it).
- No verbose narration — one status line per phase.
- Token budget target: 30K–80K per run. Hard cap: 150K — if approaching, skip the "Common patterns observed" regeneration in Phase 4.

## Failure modes (overview)

Each phase doc owns its own failure table. Cross-cutting rules:

- If `mcp__supabase__execute_sql` fails (Phase 1 SELECT) → halt + report exact error.
- If `mcp__supabase__execute_sql` fails (Phase 6 UPDATE) → save XML to `runs/<lead_id>_<datestamp>.xml`, report path, do not lose work.
- Phase 5 skill-invocation failures → ask Stefan (retry / save-as-is / abort).
- Phase 4 WebSearch / WebFetch failures → degrade gracefully, never halt the whole run.

## Out of scope (revisit later)

- Token cost / usage telemetry per run
- Slack notification when a run completes
- Bulk mode (run for N leads in one invocation)
- Per-city competitor research (second-tier cache)
- A frontend "Generate" button
