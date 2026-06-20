# Example prompts — SEO/GEO Optimizer

Invoke the agent from Claude Code in this repo. The trigger is
`Run SEO agent for <project_slug>` (close paraphrases match). Flags are optional.

---

### 1. Full run on a live client (default)

> Run SEO agent for `samir-kapsalon`

Runs phases 0–4 across every locale the project declares: loads context + prior memory,
does competitor + local intel, audits each locale (deterministic SEO + LLM-judge GEO +
local), and writes a prioritized plan — all to Supabase. Marks the run `completed` and
sets `projects.seo_enabled=true`.

### 2. Scope to a single locale

> Run SEO agent for `laurian-duma` locale en

Same pipeline, but only the English locale is audited and planned. Useful when one locale
changed and you don't want to re-spend budget on the others.

### 3. Audit only (no plan beyond the audit rows)

> Run SEO agent for `it-global-services` audit-only

Loads context, does competitor intel, and writes per-locale `seo_audits` with scores +
GATE-FACT extraction — but does not generate the prioritized `seo_plan_items` list. Use it
for a fast "where do we stand?" snapshot.

### 4. Dry run (no Supabase writes)

> Run SEO agent for `samir-kapsalon` dry-run

Runs the full reasoning (context, intel, audit, plan) and prints the results to chat, but
writes **nothing** to Supabase — no `seo_runs` row, no audits, no plan. Use it to preview
what a run would produce before committing it to the dashboard.

---

**Notes**

- If the slug is missing or unknown, the agent asks once and waits.
- The agent never pauses for permission to WebSearch / WebFetch / render / write to
  Supabase — those are pre-authorized. It only pauses on the failure modes in `AGENTS.md`.
- `articles <N>` is recognized as a flag but the article campaign itself ships in Plan 3.
