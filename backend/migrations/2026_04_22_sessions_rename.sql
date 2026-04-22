-- Applied 2026-04-22 via Supabase MCP to project xeluydwpgiddbamysgyu (CMS).
-- Renames refresh_tokens → sessions and adds observability columns for the
-- session-based auth migration. See
-- docs/superpowers/specs/2026-04-22-session-auth-design.md.

ALTER TABLE refresh_tokens RENAME TO sessions;
ALTER INDEX IF EXISTS refresh_tokens_pkey            RENAME TO sessions_pkey;
ALTER INDEX IF EXISTS refresh_tokens_token_hash_key  RENAME TO sessions_token_hash_key;
ALTER INDEX IF EXISTS refresh_tokens_user_id_fkey    RENAME TO sessions_user_id_fkey;

ALTER TABLE sessions ADD COLUMN last_used_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE sessions ADD COLUMN user_agent TEXT;
ALTER TABLE sessions ADD COLUMN ip_address TEXT;

CREATE INDEX idx_sessions_active_lookup
  ON sessions (token_hash)
  WHERE revoked = false;
