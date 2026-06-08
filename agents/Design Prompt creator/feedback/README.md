# Feedback — how it works

After every run, the agent creates a blank template in `pending/` for the lead it just processed. You edit it whenever you have something to say (no time limit — leave it for days if you want). You can also just paste your iterations directly in the Claude Code chat and the agent will record + distill them for you.

## The core idea

You take the generated prompt into Claude Design and iterate — sending correction prompts until the design is right. **Every correction you send is a signal that the *generated design prompt* under-specified something.** The agent learns from those corrections so the next prompt it writes pre-empts them. The agent improves its *prompt-writing*, not the website directly.

## Workflow

1. The agent emits `pending/lead_<id>_<date>.md` with an "Iterations" skeleton.

2. As you correct the design in Claude Design, paste each correction prompt — verbatim — under a `### Iteration N` heading:

   ```markdown
   ## Iterations sent to Claude Design

   ### Iteration 1
   Make the hero darker and drop the image carousel — it feels generic. Use a single full-bleed photo.

   ### Iteration 2
   The service prices look like a spreadsheet. Make them an editorial list, right-aligned prices, more air between rows.

   ### Iteration 3
   Still too much rounding on the buttons. Sharp corners everywhere.
   ```

3. On the agent's **next run** (any lead), Phase 2 reads all pending files, infers the recurring gap behind each iteration, and writes a lesson to `LEARNINGS.md`. Example lessons distilled from the above:
   - "For barber/salon heroes, default to a single full-bleed dark-overlay photo — never a carousel."
   - "Render service prices as a right-aligned editorial list with generous row spacing, not a dense table."
   - "Re-state the sharp-corner rule explicitly in the design_system radius block; downstream Claude keeps rounding buttons."

4. Phase 2 then archives the consumed file to `archive/<YYYY-MM>/`.

## Two ways to give feedback

- **In chat**: paste "Iteration 1: …, Iteration 2: …" straight into Claude Code. The agent interprets live, updates `LEARNINGS.md`, and — if a gap is structural — edits the relevant phase doc or the `lead-to-design-prompt` skill so the fix is permanent.
- **In the file**: write the iterations into `pending/lead_<id>_<date>.md`. Consumed on the next run.

Both routes end up in the same place: distilled lessons in `LEARNINGS.md` + (where warranted) structural edits to the agent.

## Tips for good signal

- **Paste corrections verbatim.** Don't pre-summarise — the raw correction prompt carries more signal than "I fixed the hero".
- **Order matters.** Iteration 1 → N shows what the prompt missed first vs what only surfaced late.
- **Repeated corrections across leads are gold.** If you darken the hero on three different barbershops, that's a strong default to bake into the prompt.
- **Skip the file** if you have nothing useful — an empty iterations section + the "Discard" line means Phase 2 archives without learning.
