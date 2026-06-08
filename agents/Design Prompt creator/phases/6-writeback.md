# Phase 6 — Write back

**Goal:** Persist the generated XML to `leads.design_prompt`. Create a blank feedback template so Stefan can leave lessons easily. Honor `dry-run` flag (no DB write, no template).

**Inputs:** `result_xml` from Phase 5, `lead_id` from Phase 0, `lead.business_name` from Phase 1, `mode.dry_run`.

## Steps

1. Wrap the XML in a HTML-safe envelope so the existing `DesignPromptSection` (TipTap, `dangerouslySetInnerHTML`) renders it as a code block:

   ```
   <pre><code><raw result_xml here, with & < > HTML-escaped></code></pre>
   ```

   HTML-escape rules:
   - `&` → `&amp;`
   - `<` → `&lt;`
   - `>` → `&gt;`

   (Do NOT escape inside the `<pre><code>` tags themselves — the escaping is for the XML body only.)

2. If `mode.dry_run` is set:
   - Print to chat:
     ```
     [dry-run] Would have UPDATEd leads.design_prompt for lead <id>:

     <wrapped XML, first 1000 chars + "…" if longer>

     [dry-run] Would have created agents/Design Prompt creator/feedback/pending/lead_<id>_<YYYY-MM-DD>.md
     ```
   - **Skip to step 5 (Echo).** No Supabase write, no feedback file.

3. Update Supabase via MCP:

   ```sql
   UPDATE leads
   SET design_prompt = $$<wrapped XML>$$
   WHERE id = '<lead_id>';
   ```

   (Use `$$…$$` dollar-quoting so the wrapped content's quotes/apostrophes don't need to be escaped inside the SQL string.)

   If the UPDATE returns 0 rows affected → halt + report *"Phase 6: UPDATE returned 0 rows. Lead `<id>` may have been deleted mid-run."*

   If the UPDATE fails (any other error) → fallback save:
   ```
   agents/Design Prompt creator/runs/<lead_id>_<YYYYMMDD_HHMMSS>.xml
   ```
   contains the raw XML (no `<pre><code>` wrapping). Report the path so Stefan can paste it manually.

4. Create the feedback template at `agents/Design Prompt creator/feedback/pending/lead_<lead_id>_<YYYY-MM-DD>.md`:

   ```markdown
   # Feedback — Lead <lead_id> (<business_name>)

   Generated: <YYYY-MM-DD HH:MM>

   ## How to use this file

   Paste each correction prompt you sent to Claude Design, in order, under "Iterations". Each correction is a signal that the *generated design prompt* under-specified something — the agent reads these on its next run, infers the recurring gap, and distills a lesson into `LEARNINGS.md` so future prompts pre-empt it.

   You don't have to fill the other sections — the iterations alone are enough.

   ## Iterations sent to Claude Design

   ### Iteration 1
   (paste the prompt you sent to Claude Design to fix something — verbatim)

   ### Iteration 2
   (paste the next correction prompt, if any)

   <!-- add ### Iteration 3, 4, … as you go -->

   ## (optional) Direct notes / lessons in my own words

   - (anything you want to state explicitly)

   ## (optional) Discard if not generalisable

   - Leave this line if the iterations were purely lead-specific (e.g. a typo in the address) and shouldn't become a general lesson.
   ```

   If a file with the same name already exists (re-run on same date), append `_<HHMMSS>` to the filename: `lead_<lead_id>_<YYYY-MM-DD>_<HHMMSS>.md`.

5. Echo a final line to chat:

   ```
   ✓ Written to leads.design_prompt (length: <N> chars). Feedback template: agents/Design Prompt creator/feedback/pending/lead_<lead_id>_<YYYY-MM-DD>.md
   ```

## Outputs

- `leads.design_prompt` updated for `lead_id` (unless dry-run)
- `feedback/pending/lead_<id>_<date>.md` created (unless dry-run)
- OR `runs/<id>_<datestamp>.xml` written if Supabase failed

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Supabase UPDATE returns 0 rows | "Phase 6: UPDATE returned 0 rows. Lead `<id>` may have been deleted mid-run." |
| Supabase UPDATE fails | "Phase 6: UPDATE failed (`<error>`). Saved XML to `runs/<id>_<datestamp>.xml` — paste manually." |
| Feedback template create fails | "Phase 6: could not create feedback template at `<path>` (`<error>`). The DB write succeeded; you can leave feedback by manually creating the file." |

## Self-improvement hook

If the `<pre><code>` wrapping causes rendering issues in the dashboard (e.g., HTML entities double-escaped), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Adjust wrapping/escaping in Phase 6 — current approach broke `<X>`. Triggered by: feedback on lead `<id>`.`
