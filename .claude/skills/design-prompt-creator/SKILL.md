---
name: design-prompt-creator
description: Use when the user says "Run Design Prompt Creator for lead <lead_id>" (or close paraphrase). Drives a 7-phase pipeline that researches the web for popular websites in the lead's category, invokes the lead-to-design-prompt skill with enriched context, and writes the resulting XML design prompt to leads.design_prompt via Supabase MCP. Self-learns via LEARNINGS.md (distilled feedback) and per-category research files.
---

# Design Prompt Creator (skill)

## Trigger pattern

Invoke this skill when the user message matches:

> "Run Design Prompt Creator for lead `<lead_id>` [optional hints]"

Close paraphrases match too: *"Generate design prompt for lead X"*, *"Create design brief for X"*, *"Design Prompt Creator on X"*.

If the trigger fires but `lead_id` is missing or unrecognisable, ask once for the lead id. Do not guess.

## First steps (always)

1. Read `agents/Design Prompt creator/AGENTS.md` — the workflow index + constants table.
2. Read `agents/Design Prompt creator/LEARNINGS.md` only if `wc -l` reports more than 25 lines (skip the empty scaffold to save tokens).
3. Confirm Supabase MCP is connected. The agent uses `mcp__supabase__execute_sql` with `project_id: xeluydwpgiddbamysgyu` (the `CMS` project).
4. Echo a one-line plan: *"Lead `<id>` · mode: `<flags or default>`. Phases 1–6 to follow."* Do not preview every phase.

## Lazy phase loading

Do **not** read all phase docs up front. As you enter each phase, read only that phase's file. After the phase succeeds, do not keep its content in active memory.

| Phase | When entering, Read |
|---|---|
| 0 | `agents/Design Prompt creator/phases/0-parse-intent.md` |
| 1 | `agents/Design Prompt creator/phases/1-load-lead.md` |
| 2 | `agents/Design Prompt creator/phases/2-consume-feedback.md` |
| 3 | `agents/Design Prompt creator/phases/3-check-research.md` |
| 4 | `agents/Design Prompt creator/phases/4-research.md` |
| 5 | `agents/Design Prompt creator/phases/5-generate.md` |
| 6 | `agents/Design Prompt creator/phases/6-writeback.md` |

## Token-optimization rules (binding)

- **One Read per phase doc** — do not re-Read the same phase file later in the run.
- **No verbose narration** — one status line per phase. No "Now I will..." prelude.
- **Tool output**: prefer `head_limit` and `offset` on Grep/Glob; never request full directory dumps.
- **Model policy** — defaults to whatever the user is running. No model-switching mid-run.
- **Skip the empty LEARNINGS.md** as noted above.

## Self-improvement loop

When Stefan leaves feedback in `agents/Design Prompt creator/feedback/pending/lead_<id>_*.md` after a run:

1. The NEXT run's Phase 2 picks up all pending files, distills lessons into `LEARNINGS.md`, archives the consumed files.
2. Subsequent phases use the updated `LEARNINGS.md` automatically.

The agent does NOT need an explicit "consume feedback" command. The loop runs whenever the agent runs.

## Failure mode hooks

- Halt on Supabase connect failure (Phase 1).
- Skip individual WebFetch failures (Phase 4); never halt the whole run on a single bad URL.
- On Phase 5 extraction failure, ask Stefan: retry / save-as-is / abort.
- On Phase 6 UPDATE failure, fall back to `agents/Design Prompt creator/runs/<lead_id>_<datestamp>.xml`.
