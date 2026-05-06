-- backend/migrations/2026_05_06_admin_api_keys.sql
-- Long-lived admin API keys. Plain key shown once at mint time;
-- only argon2 hash + lookup prefix stored. Auth dep argon2-verifies
-- against the row matched by key_prefix.

CREATE TABLE IF NOT EXISTS admin_api_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_prefix    text NOT NULL,
  key_hash      text NOT NULL,
  name          text NOT NULL,
  scopes        jsonb NOT NULL DEFAULT '["agent"]'::jsonb,
  last_used_at  timestamptz,
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz,
  CONSTRAINT admin_api_keys_unique_prefix UNIQUE (key_prefix)
);

CREATE INDEX IF NOT EXISTS admin_api_keys_active
  ON admin_api_keys (user_id)
  WHERE revoked_at IS NULL;

-- Lock down: only the service-role key (bypasses RLS) is allowed to
-- read/write this table. The mint script and the auth dep both use
-- the service role. The frontend's anon key has no business here.
ALTER TABLE admin_api_keys ENABLE ROW LEVEL SECURITY;
