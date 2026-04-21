-- Applied 2026-04-16 via Supabase MCP to project xeluydwpgiddbamysgyu (CMS)
-- Splits content into draft_content + published_content; adds Vercel/preview fields on projects.

ALTER TABLE content_entries RENAME COLUMN content TO published_content;
ALTER TABLE content_entries ADD COLUMN draft_content JSONB;
UPDATE content_entries SET draft_content = published_content WHERE draft_content IS NULL;

ALTER TABLE projects ADD COLUMN github_repo TEXT;
ALTER TABLE projects ADD COLUMN vercel_project_id TEXT;
ALTER TABLE projects ADD COLUMN production_url TEXT;
ALTER TABLE projects ADD COLUMN preview_url TEXT;
ALTER TABLE projects ADD COLUMN preview_token TEXT;
ALTER TABLE projects ADD COLUMN last_published_at TIMESTAMPTZ;

CREATE INDEX idx_content_entries_needs_publish
  ON content_entries (project_service_id)
  WHERE published_content IS DISTINCT FROM draft_content;
