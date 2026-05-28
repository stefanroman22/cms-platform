# Phase 0 — Parse intent

**Goal:** Extract `lead_id` and mode flags from the user's trigger prompt. Surface clarifying questions before any work.

**Inputs:** the user message that invoked the skill.

## Steps

1. Find `lead_id` in the message. Accept any uuid-like string. If missing → ask: *"Which lead? Paste id."*  Halt if no answer.

2. Scan for mode flags (case-insensitive, free placement in the message):

   | Token | Sets |
   |---|---|
   | `force fresh research` / `force research` | `mode.force_research = true` |
   | `skip research` / `cache only` | `mode.skip_research = true` |
   | `dry-run` / `dry run` | `mode.dry_run = true` |
   | `verbose` | `mode.verbose = true` |
   | `reuse structure from lead <X>` | `mode.reuse_from_lead = <X>` |
   | `style hint: <free text up to end-of-line or 200 chars>` | `mode.style_hint = <text>` |

3. If both `force fresh research` AND `skip research` are set → ask: *"You set both `force` and `skip`. Pick one."* Halt if no answer.

4. Echo a one-line plan to chat:

   ```
   Lead <id> · mode: <flags-joined-by-comma, or "default">. Phases 1–6 to follow.
   ```

## Outputs

- `lead_id` (string, required)
- `mode` dict with the 6 fields above (defaults: all false / null)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `lead_id` missing | "Which lead? Paste id." |
| Contradictory flags | "You set both `force` and `skip` research. Pick one." |

## Self-improvement hook

If a free-form flag keeps appearing in triggers that the parser doesn't recognize (e.g., `--detailed`), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Recognise `<token>` as `<mapping>`. Triggered by: <short context>.`
