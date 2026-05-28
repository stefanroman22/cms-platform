# Phase 2 — Consume feedback

**Goal:** Read all pending feedback files, distill generalisable lessons into `LEARNINGS.md`, archive the consumed files.

**Inputs:** `category_bucket` from Phase 1. Filesystem.

## Steps

1. Glob `agents/Design Prompt creator/feedback/pending/*.md`.

2. If zero files found → echo *"Phase 2: no feedback pending."* and skip to Phase 3.

3. For each file (oldest mtime first):

   a. Read the file.

   b. Identify the *generalisable lesson*. Look at the section headed `## Generalisable lesson` if present. If that section is empty or the file is marked `## (optional) Discard if not generalisable`, drop the lesson but still archive the file.

   c. Determine which heading in `LEARNINGS.md` to write under:
      - If the lesson references a specific category (the per-lead file's lead is in a category, **and** the lesson talks about category-specific patterns), use `## Category: <bucket>`.
      - Else, use `## General`.

   d. Read `LEARNINGS.md`. Compare the new lesson to existing entries under the chosen heading:
      - If a near-duplicate exists, **strengthen** (rewrite the existing entry with combined wording + today's date).
      - If a contradiction exists (says the opposite), **replace** with the newer entry + note the date so the newer one wins.
      - Otherwise, **append** as a new bullet:
        ```
        - (<YYYY-MM-DD>) <lesson text>. Triggered by: lead <id>.
        ```

   e. Write the updated `LEARNINGS.md` back.

4. Move consumed files to `agents/Design Prompt creator/feedback/archive/<YYYY-MM>/<lead_id>.md`:

   ```bash
   mkdir -p "agents/Design Prompt creator/feedback/archive/<YYYY-MM>"
   mv "agents/Design Prompt creator/feedback/pending/<file>" \
      "agents/Design Prompt creator/feedback/archive/<YYYY-MM>/<lead_id>.md"
   ```

   (If a file with the same name already exists in archive — e.g., re-feedback for the same lead — append a timestamp: `<lead_id>_<HHMMSS>.md`.)

5. Echo: *"Phase 2: consumed N feedback files, updated LEARNINGS by M entries."*

## Outputs

- `LEARNINGS.md` (updated in place)
- `feedback/pending/` (drained)
- `feedback/archive/<YYYY-MM>/` (populated)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| File is unreadable / malformed | Skip that file, leave in `pending/`, warn: *"Phase 2: skipped `<file>` (unreadable). Will retry next run."* |
| `mv` fails | Skip the move, leave file in `pending/`, warn: *"Phase 2: could not archive `<file>` — left in pending."* |

## Self-improvement hook

If a feedback file keeps getting skipped because of malformed content, append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Reject feedback files without `## Generalisable lesson` heading. Triggered by: malformed file `<path>`.`
