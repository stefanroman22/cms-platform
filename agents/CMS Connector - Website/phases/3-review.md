# Phase 3 — User review & approval

**Goal:** Human gate before any backend changes.

## Steps

1. Print the path to the report: `agents/CMS Connector - Website/cms-integration-report.md`.
2. Ask the user to review. Suggested phrasing:
   > "Integration report written to `<path>`. Review and reply 'approved' to continue, or describe what should change."
3. If user replies with corrections (not approval):
   - Update the manifest accordingly.
   - Re-write the report.
   - Append the correction to `LEARNINGS.md` under `## Phase 2 — Scan rules` so the same mistake is not made next run.
4. Loop until user replies "approved".

## Outputs

No disk writes beyond LEARNINGS.md updates.

## Token tactics

- Do **not** paste the report content into chat. Print the path only.
- When applying corrections, edit the report file in place — do not re-render the entire report unless the user asks to see the diff.
