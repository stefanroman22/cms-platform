-- Lead target-website locales. Stored as canonical English language names
-- (e.g. 'Romanian', 'Dutch'). Edited from the admin leads drawer.
ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS languages text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN leads.languages IS
'Target website locales for this lead, stored as canonical English language names (e.g. "Romanian", "Dutch"). Edited from the admin leads drawer.';

CREATE INDEX IF NOT EXISTS leads_languages_gin_idx ON leads USING gin (languages);
