---
name: cms-connector-website
description: Use when the user says "Run CMS - Connector Website agent for the project within folder <folder_name>" (or close paraphrase). Drives a 6-phase pipeline that imports a client website to GitHub, scans it for editable content, generates a markdown integration report for human review, provisions CMS services + Vercel preview, runs a test matrix, and self-improves via LEARNINGS.md.
model: claude-opus-4-8
effort: xhigh
---

# CMS Connector — Website (skill)

## Trigger pattern

Invoke this skill when the user message matches:

> "Run CMS - Connector Website agent for the project within folder `<folder_name>`"

Or close paraphrases: "Run the CMS Connector website agent on `<folder>`", "CMS-connect this site at `<folder>`", etc.

If the trigger fires but `<folder_name>` is missing or invalid, ask once for the correct path. Do not guess.

## Orchestration policy (ultracode)

This agent runs in the main Claude Code session, which has the **Workflow tool**. Operate in **ultracode style**: for substantive reasoning phases, orchestrate via the Workflow tool (multi-agent fan-out + adversarial verification) rather than reasoning solo, and be exhaustive — correctness over token cost. Specifically:
- **Phase 2 (scan/classification):** when the source is large or the content model is non-trivial, fan out parallel analysis (per page/section/service-type) and adversarially verify the proposed manifest (service shapes, locales, booking detection) before writing the report.
- **Phase 4 (integration):** orchestrate multi-agent wiring/verification when resolving service-shape or booking/UI wiring across many files.
- **Phase 5 (test-failure analysis):** fan out root-cause analysis across failing dimensions.

Effort is pinned to `xhigh` (frontmatter). For trivial single-file/single-service sites, solo execution is fine — scale the orchestration to the site's complexity.

## First steps (always)

1. Read `agents/CMS Connector - Website/AGENTS.md` — the workflow index.
2. Read `agents/CMS Connector - Website/LEARNINGS.md` only if `wc -l` reports more than 25 lines (skip the empty scaffold to save tokens).
3. Confirm credentials available before phase 1: `gh` CLI logged in (or `GITHUB_TOKEN`), `claude` CLI on PATH, `VERCEL_TOKEN`, `CMS_ADMIN_API_KEY`. If any missing, list what's needed and halt.
4. Echo a one-line plan: *"Starting CMS Connector for `<folder>`. 6 phases: GitHub repo → scan → review → integrate → test → confirm."* Do not preview every phase.

## Lazy phase loading

Do **not** read all phase docs up front. As you enter each phase, read only that phase's file. After the phase succeeds, do not keep its content in active memory — the docs stay on disk.

| Phase | When entering, Read |
|-------|---------------------|
| 1 | `agents/CMS Connector - Website/phases/1-github.md` |
| 2 | `agents/CMS Connector - Website/phases/2-scan.md` |
| 3 | `agents/CMS Connector - Website/phases/3-review.md` |
| 4 | `agents/CMS Connector - Website/phases/4-integration.md` |
| 5 | `agents/CMS Connector - Website/phases/5-testing.md` |
| 6 | `agents/CMS Connector - Website/phases/6-confirmation.md` |

## Token-optimization rules (binding)

- **One Read per phase doc** — do not re-Read the same phase file later in the run.
- **No verbose narration** — one status line per phase. No "Now I will..." prelude. No mid-step recap.
- **Tool output**: prefer `head_limit` and `offset` on Grep/Glob; never request full directory dumps.
- **Model policy** — correctness over cost on this agent. Use the most capable model available for any task that affects integration correctness:
  - Phase 2 source classification → **`claude-opus-4-8`** (default). The scan determines the entire CMS structure; an error here cascades through every later phase.
  - Phase 4 code-integration reasoning (resolving service-shape mismatches, deciding overwrite vs skip on conflicts, debugging Vercel/Resend wiring) → **`claude-opus-4-8`**.
  - Phase 5 test-failure root-cause analysis → **`claude-opus-4-8`**.
  - Trivial classification (slug derivation, framework detection from a single config file, simple yes/no decisions) → may use `claude-haiku-4-5-20251001` if the call adds <1KB context. Otherwise still Opus.
  - Never downgrade to Sonnet/Haiku to "save tokens" on integration-critical paths. The agent prioritises a clean integration over a cheap one.
- **Prompt cache**: when calling Claude API directly, mark `SYSTEM_PROMPT` with `cache_control: {"type": "ephemeral"}` so retries hit the 5-min cache.
- **Compact JSON**: `json.dumps(obj, separators=(",", ":"))` for any inter-phase payloads written to disk.
- **Skip the empty LEARNINGS.md** as noted above.
- **Don't summarize the report** in chat — print only the path. The user opens the file.

## Self-improvement loop

The agent records **both positive and negative feedback** as dated, one-line, append-only rules in `agents/CMS Connector - Website/LEARNINGS.md`. These rules are **global to the agent** — they are fed into every future run across ALL client projects, not just the project where the feedback was given.

### Negative feedback ("don't do X / always do Y")

When the user says something should have been caught, should not have been done, or a phase fails for a non-transient reason not already in LEARNINGS.md:

1. Acknowledge in one line.
2. Append a rule under the matching phase heading. Format:
   `- <YYYY-MM-DD>: <one-line rule>. Triggered by: <short context>.`
3. Re-run the affected phase if the user asks for the current run to be corrected.

When a phase fails for a non-transient reason not covered in LEARNINGS.md, append a rule on your own before retrying.

### Positive feedback ("keep doing Z / this is the preferred approach")

When Stefan explicitly praises an approach, confirms a decision was correct, or says "do this for all clients / treat this as the default": append a rule under the matching phase or area heading in the same format, prefixed with `CONFIRMED-GOOD:`. Example:

`- 2026-06-06: CONFIRMED-GOOD: heuristic-resolver pattern for contact fields praised — treat resolveContactCards as the canonical reference for all generated sites. Triggered by: Stefan confirmed it-global-services approach as preferred.`

Positive rules carry forward to all future runs exactly like negative ones — a confirmed-good behaviour is as binding as a "never do X" rule.

### Scope

Both rule types apply globally across ALL client projects. A rule written during the `it-global-services` run is active when integrating any future site. Area headings in LEARNINGS.md (`## GitHub setup`, `## Phase 2 — Scan rules`, `## Phase 4 — Integration rules`, `## Phase 5 — Testing rules`, `## Phase 6 — Onboarding rules`, `## Booking`) cover all clients.

LEARNINGS.md is **append-only** — never delete or rewrite existing rules.

## Stopping conditions

- User says "abort" / "stop" — halt cleanly, do not delete the report (user keeps for reference).
- A credential error halts the current phase only. Other phases may resume after fix.
- Rich text (ADR-0010): Phase 2 classifies every field as plain/inline/rich (repeater `inline`/`richtext`, key_value `formats`); Phase 4 §4.1.6 point 6 vendors the kit and renders via `<RichText>` (rules in `client-kit/rich-text/README.md`); Phase 5 5i includes the rich-text probe (`.cms-rich strong`/`a[href]`/`li` present, no literal tags, `strong` colour equals `--cms-rich-strong`). Never `react-markdown`.
- Test matrix failure in Phase 5 — fix, re-test, learn. Never claim Phase 6 success while any 5a–5h test is red.

## End-of-run cleanup

Phase 6 deletes:
- `agents/CMS Connector - Website/cms-integration-report.md`
- `agents/CMS Connector - Website/.last-llm-output.txt` (if present)

LEARNINGS.md is **never** deleted.
