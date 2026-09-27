# ADR-0005: Content is edited as a draft and goes live on Publish

Status: Accepted
Date: 2026-09-27

## Context

Clients edit their own website content in the dashboard. They save often, make mistakes, and need
to see a change before their visitors do. Client sites fetch content at build or request time from
the backend, so whatever the public endpoint returns is live.

## Decision

- Each `content_entries` row has two columns: `draft_content` (what the dashboard edits) and
  `published` (what the public sees).
- Saving in the dashboard only changes `draft_content`. `POST /projects/{slug}/publish`
  (`routers/publish.py`) copies draft to published for the project.
- Public reads (`GET /content/{slug}` and `/content/{slug}/{locale}` in `routers/content.py`)
  return only published content, with an ETag and `no-cache` so clients revalidate cheaply.
- Each client site's preview deployment (its `cms-preview` branch) reads
  `/content/{slug}/draft` using the project's `preview_token`, so the dashboard's "See Preview"
  shows unpublished changes.

## Consequences

- Clients can edit safely; nothing reaches visitors until they click Publish.
- A common support issue: "my edit doesn't show" usually means it was not published, or the client
  site does not read that service at all.
- The preview link only works if the client's `cms-preview` branch is current and its Vercel
  preview is public (see ADR-0006).
- Do NOT: make dashboard saves write `published` directly, have public endpoints fall back to draft
  content, or remove the preview token check on the draft endpoints.
