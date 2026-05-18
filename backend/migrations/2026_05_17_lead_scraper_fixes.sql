-- Follow-up to 2026_05_17_lead_scraper.sql — 2026-05-17
-- Addresses code-review feedback: scrape_jobs needs updated_at + trigger
-- (parity with leads table) and triggered_by needs a CHECK constraint
-- (soft enum, prevent drift).

-- ────────────────────────────────────────────────────────────────────
-- 1. scrape_jobs.triggered_by CHECK
-- ────────────────────────────────────────────────────────────────────
ALTER TABLE scrape_jobs
    ADD CONSTRAINT scrape_jobs_triggered_by_check
    CHECK (triggered_by IN ('cms', 'cron', 'manual'));

-- ────────────────────────────────────────────────────────────────────
-- 2. scrape_jobs.updated_at + trigger
-- ────────────────────────────────────────────────────────────────────
ALTER TABLE scrape_jobs
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION scrape_jobs_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scrape_jobs_updated_at_trigger
    BEFORE UPDATE ON scrape_jobs
    FOR EACH ROW EXECUTE FUNCTION scrape_jobs_set_updated_at();
