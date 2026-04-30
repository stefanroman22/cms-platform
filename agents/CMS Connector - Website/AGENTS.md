# CMS Connector — Website Agent

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/cms-connector-website/SKILL.md`](../../.claude/skills/cms-connector-website/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

> "Run CMS - Connector Website agent for the project within folder `<folder_name>`"

Loaded from SKILL.md. See SKILL.md for first steps and token rules.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|-------|-----|------|
| 1 | GitHub repo | [phases/1-github.md](./phases/1-github.md) | New repo populated from `<folder_name>` |
| 2 | Scan + report | [phases/2-scan.md](./phases/2-scan.md) | Markdown integration report for human review |
| 3 | Review | [phases/3-review.md](./phases/3-review.md) | User approval gate (no disk writes) |
| 4 | Integration | [phases/4-integration.md](./phases/4-integration.md) | Provision CMS services, wire Resend, set up Vercel |
| 5 | Testing | [phases/5-testing.md](./phases/5-testing.md) | End-to-end test matrix passes |
| 6 | Client onboarding + confirmation | [phases/6-confirmation.md](./phases/6-confirmation.md) | Create client account, transfer project ownership, send branded welcome email via Resend, delete temp files, print summary |

Each phase doc contains: goal, inputs, steps, outputs, failure messages, self-improvement hook.

## Required credentials

| Tool | Var | Used in |
|------|-----|---------|
| GitHub MCP | `GITHUB_TOKEN` | 1, 4 |
| Anthropic Claude | `claude` CLI preferred; `ANTHROPIC_API_KEY` fallback | 2, 5 (failure analysis only) |
| Vercel MCP | `VERCEL_TOKEN` | 4 |
| Supabase Management | `SUPABASE_ACCESS_TOKEN` (PAT, `sbp_*`) | 4 (project-row insert), 6 (ownership transfer) |
| Resend | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | 4 (email_config wiring; backend Vercel env), 6 (welcome email — agent calls Resend directly) |
| CMS admin | `sid` cookie of an admin user, OR an admin API key once C is built | 4, 5, 6 |

If a credential needed by a phase is missing, **halt that phase**, surface a clear remediation, do not silently skip.

## Failure-mode taxonomy

| Class | Action | Self-improve? |
|-------|--------|---------------|
| Transient (network, 5xx, rate-limit) | Retry up to 3× with backoff. Surface only after exhaustion. | No |
| Credential (401/403, missing env) | Halt, surface remediation. | Only if config drifts repeatedly |
| Logical (wrong service type, missed section) | Surface, ask user, fix, learn. | Always |
| Schema mismatch (CMS service shape changed) | Halt. Re-read backend before extending. | Always |
| User-induced (bad path, malformed input) | Re-prompt. | No |

## Hard rules — what is / isn't a CMS service

**Always include** (Phase 2 surfaces them as candidates):
- General section: display name, logo if `<folder_name>/public/` has one
- Contact: email, phone, location, schedule (if business has hours)
- Domain-specific sections: about, hobbies, projects, experience (portfolio); menu (food/drink); about-us text; service catalogue (if business sells services — every per-service field must map to a repeater field)

**Never include**:
- Button / CTA labels
- Navigation items
- Page-level routes / page metadata
- Hard-coded UI affordance copy ("Loading…", "Subscribe", form-field placeholders)
- Class names, design tokens, animation config, breakpoints
- Test fixtures, mock data

**Decision rule when ambiguous**: "would a non-developer client reasonably ask 'can I change this myself?'" → include. Else exclude.

These hard rules are **also enforced** in `prompts.py` SYSTEM_PROMPT. Keep both in sync.

## Glossary

- **Service** — CMS content unit. Eight types: `text_block`, `image`, `gallery`, `video`, `file_download`, `key_value`, `email_config`, `repeater`.
- **Manifest** — JSON the agent emits. Slim variant `cms.config.json` (in client repo), full variant `cms-provision.json` (admin keeps).
- **Preview token** — opaque string in `VITE_CMS_PREVIEW_TOKEN` authenticating draft-content reads.
- **`folder_name`** — directory containing client website source.
- **`<folder_name>/public/`** — static assets, where the logo lives.

## Modifying this agent

If you change Phase 2 hard rules: update `prompts.py` SYSTEM_PROMPT to match.
If you change Phase 4 sub-steps: update the reference implementations in `scan.py` (`_provision`, `_vercel_setup`).
If you change failure messages: update the corresponding phase doc and any tests in `tests/`.
LEARNINGS.md is append-only; never edit existing rules.
