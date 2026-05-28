# Feedback — how it works

After every run, the agent creates a blank template in `pending/` for the lead it just processed. You edit it whenever you have something to say (no time limit — leave it for days if you want).

## Workflow

1. The agent emits `pending/lead_<id>_<date>.md` with this skeleton:

   ```markdown
   # Feedback — Lead <id> (<business_name>)

   Generated: <date>

   ## What I changed before sending to Claude Design

   - …

   ## Why

   - …

   ## Generalisable lesson

   - …

   ## (optional) Discard if not generalisable

   - Leave this section if the change was purely lead-specific
   ```

2. You review the prompt in the dashboard / claude.ai/design. If you edit anything before sending it to Claude Design, jot the change + the reason here.

3. **Most important section**: `## Generalisable lesson`. The agent's Phase 2 reads this on the next run and distills it into `LEARNINGS.md`. If the change was purely lead-specific (e.g., "lead is in Amsterdam, swapped the city name in copy"), leave the `## (optional) Discard if not generalisable` line — the agent will drop the lesson but still archive the file.

4. Next time you run the agent (any lead), Phase 2 picks up ALL pending files, updates `LEARNINGS.md`, and moves them to `archive/<YYYY-MM>/`.

## Tips for good lessons

- **Specific over vague.** "Default away from Inter for boutique cafes" beats "use better fonts".
- **Sourced.** The agent auto-adds the date + lead id when it copies your lesson into LEARNINGS.
- **One lesson per file.** If you have multiple unrelated lessons, edit the file to list each clearly so Phase 2 distills them as separate entries.
- **Skip the file** if you have nothing useful to say. Empty `## Generalisable lesson` + the discard line means Phase 2 archives without learning anything.
