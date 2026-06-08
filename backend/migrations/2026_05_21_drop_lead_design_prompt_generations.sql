-- Rolls back the lead_design_prompt_generations table and its enum.
-- Tasks 1–12 from the prior dashboard-driven attempt have been superseded
-- by the Design Prompt Creator agent (see docs/superpowers/plans/
-- 2026-05-21-design-prompt-creator-agent.md). The agent writes XML to
-- the existing leads.design_prompt column directly via Supabase MCP.

DROP TABLE IF EXISTS lead_design_prompt_generations;
DROP TYPE IF EXISTS lead_design_prompt_generation_status;
