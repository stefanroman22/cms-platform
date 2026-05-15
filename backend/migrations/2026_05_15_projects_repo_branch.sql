-- 2026_05_15 — projects.repo_branch
-- Adds the branch name agents (S3) will push fixes to. Defaults to 'dev'
-- because that's the preview-deploy branch in this project's workflow.
-- RLS: covered by existing projects_owner_* policies; no new policy needed.

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS repo_branch TEXT NOT NULL DEFAULT 'dev';

COMMENT ON COLUMN projects.repo_branch IS
  'Git branch the issue-solver agent pushes fixes to (dev = preview deploy).';
