-- Lead closed-deal amount (editable only when lead_status='accepted')
-- + timestamp of first non-null closed_amount write (revenue-over-time
-- queries group by this column).

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS closed_amount NUMERIC(12,2) CHECK (closed_amount IS NULL OR closed_amount >= 0),
    ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

COMMENT ON COLUMN leads.closed_amount IS
'Deal value in EUR. Writable only when lead_status=''accepted''; backend enforces this.';
COMMENT ON COLUMN leads.closed_at IS
'Set automatically when closed_amount transitions from NULL to a value. Drives revenue-over-time aggregation.';

CREATE INDEX IF NOT EXISTS leads_closed_at_idx ON leads (closed_at);
CREATE INDEX IF NOT EXISTS leads_closed_amount_idx ON leads (closed_amount);
