-- Lead scraper schema — 2026-05-17
-- See spec: docs/superpowers/plans/2026-05-17-google-maps-lead-scraper.md

-- ────────────────────────────────────────────────────────────────────
-- 1. Enums
-- ────────────────────────────────────────────────────────────────────
CREATE TYPE lead_type AS ENUM ('website', 'automation', 'both');
CREATE TYPE web_presence AS ENUM ('none', 'social_only', 'has_website', 'unknown');
CREATE TYPE website_build_status AS ENUM (
    'not_started', 'building_design', 'design_done',
    'building', 'finished_cms', 'refining', 'not_applicable'
);
CREATE TYPE ai_workflow_status AS ENUM (
    'not_started', 'building', 'finished', 'refining', 'not_applicable'
);
CREATE TYPE lead_status AS ENUM ('not_sent', 'sent', 'accepted', 'refused');
CREATE TYPE lead_contact_type AS ENUM ('not_contacted', 'phone', 'mail', 'in_person');
CREATE TYPE payment_status AS ENUM ('not_applicable', 'not_paid', 'paid');
CREATE TYPE scrape_job_status AS ENUM ('pending', 'running', 'done', 'failed', 'cancelled');

-- ────────────────────────────────────────────────────────────────────
-- 2. scrape_jobs queue table
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE scrape_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          scrape_job_status NOT NULL DEFAULT 'pending',
    params          JSONB NOT NULL,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    results_found   INT,
    results_inserted INT,
    results_skipped INT,
    error           TEXT,
    triggered_by    TEXT NOT NULL DEFAULT 'cms'
);

CREATE INDEX scrape_jobs_status_created_idx ON scrape_jobs (status, created_at);

COMMENT ON TABLE scrape_jobs IS
'Queue between the CMS admin form and the Hetzner scraper worker. Worker picks status=pending oldest-first.';
COMMENT ON COLUMN scrape_jobs.params IS
'ScrapeParams pydantic model serialised to JSON. Validated by the API before insert.';

-- ────────────────────────────────────────────────────────────────────
-- 3. leads table
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE leads (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- provenance
    external_id           TEXT NOT NULL UNIQUE,
    scrape_job_id         UUID REFERENCES scrape_jobs(id) ON DELETE SET NULL,
    primary_source        TEXT NOT NULL DEFAULT 'google_maps',
    source_url            TEXT,
    -- classification
    lead_type             lead_type NOT NULL DEFAULT 'website',
    category              TEXT,
    -- identity
    business_name         TEXT NOT NULL,
    name_normalized       TEXT NOT NULL,
    description           TEXT,
    about                 TEXT,
    -- location
    country               TEXT,
    region                TEXT,
    city                  TEXT,
    address               TEXT,
    postal_code           TEXT,
    lat                   DOUBLE PRECISION,
    lng                   DOUBLE PRECISION,
    -- contact / links
    phone                 TEXT,
    email                 TEXT,
    website_url           TEXT,
    facebook_url          TEXT,
    instagram_url         TEXT,
    menu_url              TEXT,
    -- digital presence
    web_presence          web_presence NOT NULL DEFAULT 'unknown',
    -- reviews / hours / photos
    rating                NUMERIC(2,1),
    review_count          INT,
    reviews               JSONB,
    opening_hours         JSONB,
    photo_urls            TEXT[],
    -- pipeline status
    website_build_status  website_build_status NOT NULL DEFAULT 'not_started',
    ai_workflow_status    ai_workflow_status   NOT NULL DEFAULT 'not_started',
    lead_status           lead_status          NOT NULL DEFAULT 'not_sent',
    lead_contact_type     lead_contact_type    NOT NULL DEFAULT 'not_contacted',
    payment_status        payment_status       NOT NULL DEFAULT 'not_applicable',
    -- AI scoring (future agent)
    ai_score              INT CHECK (ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)),
    ai_recommendation     TEXT,
    ai_reasoning          TEXT,
    ai_scored_at          TIMESTAMPTZ,
    -- extensibility
    extra                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes                 TEXT,
    -- timestamps
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX leads_city_idx           ON leads (city);
CREATE INDEX leads_country_idx        ON leads (country);
CREATE INDEX leads_category_idx       ON leads (category);
CREATE INDEX leads_web_presence_idx   ON leads (web_presence);
CREATE INDEX leads_lead_status_idx    ON leads (lead_status);
CREATE INDEX leads_lead_type_idx      ON leads (lead_type);
CREATE INDEX leads_rating_idx         ON leads (rating);
CREATE INDEX leads_scrape_job_id_idx  ON leads (scrape_job_id);

COMMENT ON TABLE leads IS
'One row per business discovered by the scraper. external_id is the dedup key (Google feature id or fallback hash).';
COMMENT ON COLUMN leads.extra IS
'Extensibility seam — new extracted fields, AI scoring intermediate values, new lead_type signals all land here without schema migrations.';

-- ────────────────────────────────────────────────────────────────────
-- 4. updated_at trigger
-- ────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION leads_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at_trigger
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION leads_set_updated_at();

-- ────────────────────────────────────────────────────────────────────
-- 5. RLS
-- The scraper uses the service-role key and bypasses RLS. The CMS API
-- routes use the service-role key + app-layer admin checks. So RLS is
-- enabled with no permissive policies — any anon access fails closed.
-- ────────────────────────────────────────────────────────────────────
ALTER TABLE leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_jobs  ENABLE ROW LEVEL SECURITY;

-- Stub for future authenticated-admin direct access from the frontend
-- (kept commented; CMS goes through FastAPI which uses service-role).
-- CREATE POLICY "Admins can read leads"
--   ON leads FOR SELECT TO authenticated
--   USING (EXISTS (SELECT 1 FROM users WHERE users.id = auth.uid() AND users.is_admin));
