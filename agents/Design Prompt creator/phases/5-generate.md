# Phase 5 — Generate

**Goal:** Invoke the existing `lead-to-design-prompt` skill with the lead JSON enriched with research insights + LEARNINGS lessons + Stefan's hints. Extract the fenced XML block from the skill's output.

**Inputs:** `lead` from Phase 1, `research_content_for_phase_5` from Phase 4 (may be empty if Phase 4 was skipped), `mode.style_hint` and `mode.reuse_from_lead` from Phase 0, current `LEARNINGS.md`.

## Steps

1. Build the additional-context block:

   ```markdown
   <additional_context>

   ## Research insights for this category

   <copy "Common patterns observed" block from research/<bucket>.md
    + 3-5 most relevant brand summaries — pick by archetype match
    with the lead's likely archetype>

   ## Lessons from prior runs

   <copy the "## General" section of LEARNINGS.md
    + the "## Category: <bucket>" section of LEARNINGS.md
    — verbatim, retain dates>

   ## Style hints from the trigger

   <if mode.style_hint is set, paste it here. Otherwise omit this section entirely.>

   ## Reference prompt to follow structure from

   <if mode.reuse_from_lead is set:
     1. Call mcp__supabase__execute_sql:
        SELECT design_prompt FROM leads WHERE id = '<reuse_from_lead>';
     2. If result is null/empty → ask: "Lead <X> has no design_prompt set. Pick a different reference, or proceed without?"
        - If "without", omit this section entirely.
        - If user picks another lead, retry with that one.
     3. If non-null:
        - Strip <pre><code>…</code></pre> wrapper if present (same regex as Phase 1).
        - Paste the raw stripped content here, fenced as ```xml … ```.
    Otherwise omit this section entirely.>

   </additional_context>
   ```

2. Build the prompt to send to the `Skill` tool (target: `lead-to-design-prompt`):

   ```
   Generate a design prompt for this lead:

   ```json
   <lead JSON from Phase 1, pretty-printed with indent=2>
   ```

   <additional_context block from step 1>
   ```

3. Invoke the skill via the `Skill` tool. The `lead-to-design-prompt` skill returns Markdown that includes one fenced ` ```xml ` code block.

4. Extract the first fenced ` ```xml ` block from the skill's output using regex:

   ```
   ```xml\n(.*?)\n```
   ```

   (DOTALL flag; first match wins.)

5. If extraction fails (no fenced xml block) → show the first 500 chars of the skill output and ask: *"The skill output has no ```xml block. Retry / save-as-is / abort?"*  Halt for answer.

6. **Universal-block sanity check.** Grep the extracted XML for these four tags:
   `<universal_ux_requirements>`, `<intro_loader>`, `<themed_scrollbar>`, `<page_transitions>`.
   These are non-negotiable, category-agnostic baseline UX behaviours every build must ship
   (intro loader, themed scrollbar, smooth page-fade transitions).
   - If ANY tag is missing → echo: *"Phase 5: extracted XML is missing `<tagname>`. The skill must emit `<universal_ux_requirements>` literally from `references/prompt-skeleton.xml.md`. Retry / save-as-is / abort?"* Halt for answer.
   - On retry, re-invoke the skill once. If still missing on retry, default to **abort** — do not silently writeback a non-conformant prompt.

7. Echo: *"Phase 5: generated `<N>` chars of XML."*

## Outputs

- `result_xml` — the extracted raw XML content

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Skill invocation fails | "Phase 5: lead-to-design-prompt skill failed: `<error>`. Retry?" Halt. |
| No fenced xml block in output | "Phase 5: model output has no `\`\`\`xml` block. First 500 chars: `<excerpt>`. Retry / save-as-is / abort?" Halt. |
| Missing universal UX block | "Phase 5: extracted XML is missing `<tagname>`. The skill must emit `<universal_ux_requirements>` literally from `references/prompt-skeleton.xml.md`. Retry / save-as-is / abort?" Retry once → on second miss, default abort. |
| `reuse_from_lead` references a missing prompt | "Lead `<X>` has no `design_prompt`. Pick a different reference, or proceed without?" |

## Self-improvement hook

If Phase 5 keeps producing XML that Stefan then heavily edits (large diffs noted in feedback files), append to `LEARNINGS.md` under `## General` or the matching category section:
- `- <YYYY-MM-DD>: For `<context>`, the skill defaults to `<X>` but Stefan consistently prefers `<Y>`. Triggered by: feedback on N leads.`
