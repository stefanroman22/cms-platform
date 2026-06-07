# Review Log

Append one dated entry per review run. Newest first. Keeps a history of *how the posture
changed* over time, independent of the per-finding tracker.

---

## 2026-06-07 — Baseline full review

- **Method:** 14-dimension multi-agent workflow (find → adversarial verification → synthesize), 84 agents.
- **Scope:** full codebase — frontend (incl. embeddable booking widget), backend (15 routers, 30+ services, core auth/session/limiter), 26 SQL migrations, 8 GitHub Actions workflows, 4 AI agents, the scraper, dependencies, and live Supabase + Vercel state via MCP.
- **Live MCP state pulled:** Supabase security advisors on `xeluydwpgiddbamysgyu` (RLS-disabled `slack_processed_events`, `SECURITY DEFINER` view `tenant_rls_status`, anon/authenticated-executable `claim_*_solver_issue` RPCs, mutable function search_path, leaked-password protection disabled); Vercel project `cms-backend-roman` confirmed.
- **Result:** 55 confirmed findings (1 critical, 3 high, 10 medium, 31 low, 10 info); 14 candidates adversarially dismissed as false positives (see [`dismissed.md`](./dismissed.md)).
- **Headline:** `SEC-001` critical — client issue text → prompt-injection → RCE on the Solver CI runner with live write tokens. Dominant theme: the agentic/CI automation layer + public Supabase `anon` surface, not the internet-facing edges.
- **Status:** baseline — all findings `open`, none fixed yet.
- **Notes / gaps:** Vercel `list_projects` returned empty for the team scope (project reachable directly via `get_project`); frontend project env-scoping reviewed from repo config. The prior 109-finding audit (`docs/superpowers/specs/2026-05-07-security-audit.md`) predates the booking/multi-language/scraper/marketing code, which was the newly-audited surface here.

<!-- Next entry template:

## YYYY-MM-DD — Weekly scheduled review
- Method / scope:
- Since last review (new code scanned):
- New findings: SEC-NNN …
- Status changes: SEC-NNN open→fixed (commit …), …
- MCP state deltas (advisors resolved/new):
- Headline + remaining top risks:
-->
