-- CMS multi-language Phase 1: add a per-locale dimension to content.
-- Behavior-preserving: existing single-locale content is tagged with each
-- project's default locale; the one-row-per-service uniqueness becomes
-- one-row-per-(service, locale).

-- 1. Per-project locale configuration.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS default_locale text NOT NULL DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS locales        text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN projects.default_locale IS
    'The language the client authors in; the source for auto-translation.';
COMMENT ON COLUMN projects.locales IS
    'All locales this project publishes; default_locale listed first.';

-- 2. content_entries locale dimension + per-leaf override tracking.
ALTER TABLE content_entries
    ADD COLUMN IF NOT EXISTS locale           text,
    ADD COLUMN IF NOT EXISTS translation_meta jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN content_entries.locale IS
    'ISO-639/BCP-47 locale code for this content row. One row per (service, locale).';
COMMENT ON COLUMN content_entries.translation_meta IS
    'Per-leaf override tracking: { "<leaf-path>": { "src_hash": "..." } }. Only manually-overridden leaves appear.';

-- 3. Backfill existing rows to their project's default locale.
UPDATE content_entries ce
SET locale = p.default_locale
FROM project_services ps
JOIN projects p ON p.id = ps.project_id
WHERE ce.project_service_id = ps.id
  AND ce.locale IS NULL;

-- 4. Initialise projects.locales = [default_locale] where still empty.
UPDATE projects
SET locales = ARRAY[default_locale]
WHERE cardinality(locales) = 0;

-- 4b. Safety net: backfill any content_entries row the join above didn't cover
--     (orphan / edge case) so the NOT NULL below can never abort the migration.
UPDATE content_entries SET locale = 'en' WHERE locale IS NULL;

-- 5. Enforce NOT NULL now that every row is backfilled.
ALTER TABLE content_entries ALTER COLUMN locale SET NOT NULL;

-- 6. Swap the one-to-one uniqueness for per-(service, locale) uniqueness.
--    Drop whatever the existing UNIQUE(project_service_id) constraint is named.
DO $$
DECLARE conname text;
BEGIN
    SELECT con.conname INTO conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'content_entries'
      AND con.contype = 'u'
      AND con.conkey = (
          SELECT array_agg(att.attnum)
          FROM pg_attribute att
          WHERE att.attrelid = rel.oid AND att.attname = 'project_service_id'
      );
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE content_entries DROP CONSTRAINT %I', conname);
    END IF;
END $$;

ALTER TABLE content_entries
    ADD CONSTRAINT content_entries_service_locale_key UNIQUE (project_service_id, locale);
