-- Drop the two AI placeholder columns (ai_recommendation, ai_reasoning) — they
-- were never populated and the admin UI now surfaces a single design_prompt
-- field instead. ai_score and ai_scored_at remain.

ALTER TABLE leads
    DROP COLUMN IF EXISTS ai_recommendation,
    DROP COLUMN IF EXISTS ai_reasoning,
    ADD COLUMN IF NOT EXISTS design_prompt TEXT;

COMMENT ON COLUMN leads.design_prompt IS
'Long-form prompt that drives AI website design generation for this lead. Populated by an external agent.';
