# Design Prompt Creator Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `agents/Design Prompt creator/` plus `.claude/skills/design-prompt-creator/SKILL.md` — a local, Claude-Code-triggered agent that turns one SMB lead into an XML design prompt (via the existing `lead-to-design-prompt` skill enriched with web research + accumulated learnings), then writes it to `leads.design_prompt`. Also revert Tasks 1–12 from the prior dashboard-based attempt.

**Architecture:** Pure-markdown agent. Trigger via Claude Code skill → 7 phases (0–6) of markdown contracts that Claude follows using its native tools (Read, Edit, Glob, WebSearch, WebFetch, Skill, `mcp__supabase__execute_sql`, Bash). No Python modules, no tests, no GitHub Actions. Self-learning through `LEARNINGS.md` (distilled feedback) and `research/<category>.md` (compound reference library).

**Tech Stack:** Markdown + Claude Code tools + Supabase MCP. The agent invokes the existing `lead-to-design-prompt` skill at `.claude/skills/lead-to-design-prompt/`.

**Spec:** [docs/superpowers/specs/2026-05-21-design-prompt-creator-agent-design.md](../specs/2026-05-21-design-prompt-creator-agent-design.md). Read it before starting Task 1.

---

## Conventions (read once, apply throughout)

- **No git commit.** Every task ends with `git add` (stage only). Stefan commits explicitly when ready. (Overrides the writing-plans template's commit steps.)
- **Repo path has spaces:** `c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites` — quote it in shell commands.
- **Branch:** `feat/lead-scraper-system` (safe, not master).
- **Supabase project_id:** `xeluydwpgiddbamysgyu` (the `CMS` project — verified earlier in the brainstorming session).
- **Path with spaces in file paths:** the agent folder is literally `agents/Design Prompt creator/` (spaces, lowercase `c` in creator). Match existing pattern (`agents/Solver - Issues/`, `agents/CMS Connector - Website/`).
- **Apply migrations via Supabase MCP** (`mcp__supabase__apply_migration`), not via psql.
- **No tests in this plan.** The agent is a markdown contract; there's nothing to unit-test.

---

## File Structure (locked decisions)

### Cleanup — delete or revert

| Path | Action |
|---|---|
| Supabase table `lead_design_prompt_generations` + enum | DROP via new migration |
| `backend/migrations/2026_05_21_lead_design_prompt_generations.sql` | Delete file |
| `backend/auth_service/services/design_prompt_dispatch.py` | Delete |
| `backend/auth_service/tests/test_design_prompt_dispatch.py` | Delete |
| `backend/auth_service/tests/test_design_prompt_schemas.py` | Delete |
| `backend/auth_service/tests/test_admin_design_prompt_router.py` | Delete |
| `backend/auth_service/models/schemas.py` | Revert: drop 3 Pydantic models + Literal + `Any` import addition |
| `backend/auth_service/routers/admin_leads.py` | Revert: drop the schema/dispatch imports, the whitelist helper, and the 3 new endpoints |
| `scripts/generate_design_prompt.py` | Delete |
| `scripts/tests/__init__.py` | Delete |
| `scripts/tests/test_generate_design_prompt.py` | Delete |
| `.github/workflows/generate-design-prompt.yml` | Delete |
| `frontend/src/components/admin/leads/hooks/useDesignPromptGenerations.ts` | Delete |
| `frontend/src/components/admin/leads/hooks/__tests__/useDesignPromptGenerations.test.ts` | Delete |
| `frontend/src/components/admin/leads/sections/GeneratedDesignPromptSection.tsx` | Delete |
| `frontend/src/components/admin/leads/sections/__tests__/GeneratedDesignPromptSection.test.tsx` | Delete |
| `frontend/src/components/admin/leads/types.ts` | Revert: drop 3 new types |
| `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` | Revert: drop import + JSX line |
| `docs/superpowers/specs/2026-05-21-generate-design-prompt-design.md` | Delete |
| `docs/superpowers/plans/2026-05-21-generate-design-prompt.md` | Delete |

### Build — create

| Path | Responsibility |
|---|---|
| `backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql` | Records the rollback migration |
| `agents/Design Prompt creator/AGENTS.md` | Authoritative agent spec |
| `agents/Design Prompt creator/README.md` | 1-page quick reference |
| `agents/Design Prompt creator/LEARNINGS.md` | Empty skeleton (auto-grown) |
| `agents/Design Prompt creator/phases/0-parse-intent.md` | Phase 0 contract |
| `agents/Design Prompt creator/phases/1-load-lead.md` | Phase 1 contract |
| `agents/Design Prompt creator/phases/2-consume-feedback.md` | Phase 2 contract |
| `agents/Design Prompt creator/phases/3-check-research.md` | Phase 3 contract |
| `agents/Design Prompt creator/phases/4-research.md` | Phase 4 contract |
| `agents/Design Prompt creator/phases/5-generate.md` | Phase 5 contract |
| `agents/Design Prompt creator/phases/6-writeback.md` | Phase 6 contract |
| `agents/Design Prompt creator/research/{restaurant,cafe,salon,venue,retail,service}.md` | 6 empty skeletons |
| `agents/Design Prompt creator/feedback/README.md` | How to leave feedback |
| `agents/Design Prompt creator/feedback/pending/.gitkeep` | Empty queue |
| `agents/Design Prompt creator/feedback/archive/.gitkeep` | Empty archive |
| `agents/Design Prompt creator/runs/.gitkeep` | Fallback-save dir |
| `.claude/skills/design-prompt-creator/SKILL.md` | Trigger + first steps |

### Untouched

- `leads.design_prompt` column (agent writes to it; existing TipTap-rendered HTML lives here)
- `frontend/src/components/admin/leads/sections/DesignPromptSection.tsx` (becomes the review/edit surface for the agent's output)
- `.claude/skills/lead-to-design-prompt/` (agent invokes it via Skill tool)

---

## Task 1: Cleanup — Supabase

Drop the table + enum created by Tasks 1–12. New migration file records the rollback for any future fresh deploy.

**Files:**
- Create: `backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql`
- Delete (via `git rm`): `backend/migrations/2026_05_21_lead_design_prompt_generations.sql`

- [ ] **Step 1: Write the rollback migration SQL**

Create `backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql`:

```sql
-- Rolls back the lead_design_prompt_generations table and its enum.
-- Tasks 1–12 from the prior dashboard-driven attempt have been superseded
-- by the Design Prompt Creator agent (see docs/superpowers/plans/
-- 2026-05-21-design-prompt-creator-agent.md). The agent writes XML to
-- the existing leads.design_prompt column directly via Supabase MCP.

DROP TABLE IF EXISTS lead_design_prompt_generations;
DROP TYPE IF EXISTS lead_design_prompt_generation_status;
```

- [ ] **Step 2: Apply via Supabase MCP**

Call:
```
mcp__supabase__apply_migration
  project_id: xeluydwpgiddbamysgyu
  name: drop_lead_design_prompt_generations
  query: <contents of the SQL file above>
```

- [ ] **Step 3: Verify table is gone**

Call:
```
mcp__supabase__list_tables  project_id: xeluydwpgiddbamysgyu  schemas: ["public"]  verbose: false
```

Confirm `lead_design_prompt_generations` is NOT in the list.

- [ ] **Step 4: Delete the original migration file (it's still staged from Tasks 1–12)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git rm -f backend/migrations/2026_05_21_lead_design_prompt_generations.sql
```

- [ ] **Step 5: Stage the rollback migration (no commit)**

```bash
git add backend/migrations/2026_05_21_drop_lead_design_prompt_generations.sql
```

---

## Task 2: Cleanup — Backend (delete + revert)

Remove the FastAPI additions from Tasks 2–6.

**Files:**
- Delete: `backend/auth_service/services/design_prompt_dispatch.py`
- Delete: `backend/auth_service/tests/test_design_prompt_dispatch.py`
- Delete: `backend/auth_service/tests/test_design_prompt_schemas.py`
- Delete: `backend/auth_service/tests/test_admin_design_prompt_router.py`
- Revert (manual edits): `backend/auth_service/models/schemas.py`
- Revert (manual edits): `backend/auth_service/routers/admin_leads.py`

- [ ] **Step 1: Delete the new service + test files**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git rm -f backend/auth_service/services/design_prompt_dispatch.py \
          backend/auth_service/tests/test_design_prompt_dispatch.py \
          backend/auth_service/tests/test_design_prompt_schemas.py \
          backend/auth_service/tests/test_admin_design_prompt_router.py
```

- [ ] **Step 2: Revert `backend/auth_service/models/schemas.py`**

The Tasks 2 additions are at the bottom (the `# ── Design-prompt generations ──` section). Open the file and DELETE these blocks:

```python
# ── Design-prompt generations ───────────────────────────────────────────────

DesignPromptGenerationStatus = Literal["pending", "running", "done", "failed"]


class DesignPromptGenerationOut(BaseModel):
    id: str
    lead_id: str
    status: DesignPromptGenerationStatus
    result_xml: str | None = None
    error_message: str | None = None
    input_snapshot: dict[str, Any]
    triggered_by: str | None = None
    model: str
    skill_version: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class DesignPromptGenerationsListOut(BaseModel):
    items: list[DesignPromptGenerationOut]
    total: int


class DesignPromptGenerationPatch(BaseModel):
    # 200 KB cap — the skill output is typically 20–40 KB.
    result_xml: str = Field(min_length=1, max_length=200 * 1024)
```

Also, the typing import was extended from `Annotated, Literal` to `Annotated, Any, Literal` during Task 2's fix-up. Revert the import to its original form:

```python
from typing import Annotated, Literal
```

(If `Any` is still used elsewhere in the file after the deletion above, keep it — but it was added specifically for `input_snapshot: dict[str, Any]`, so safe to drop.)

- [ ] **Step 3: Revert `backend/auth_service/routers/admin_leads.py`**

Three editorial pieces to remove. Open the file and:

a) Restore the imports block to its pre-Task-4 form:

```python
from ..models.schemas import LeadOut, LeadUpdate
from ..services.html_sanitizer import sanitize_design_prompt
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid
```

(Drop the `DesignPromptGeneration*` schema imports and the `design_prompt_dispatch` import.)

b) Delete the `_SKILL_INPUT_WHITELIST` tuple and `_build_skill_input` function (added above `router = APIRouter(...)` in Task 4).

c) Delete the three new endpoints at the bottom of the file:
- `generate_design_prompt` (POST)
- `list_design_prompt_generations` (GET)
- `patch_design_prompt_generation` (PATCH)

The file should end after the `patch_lead` endpoint (line ~141 in the pre-Tasks-4-6 state).

- [ ] **Step 4: Verify backend tests still pass (smoke check that nothing broke)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/backend" && source venv/Scripts/activate && pytest auth_service/tests/test_admin_leads_router.py -v
```

Expected: all leads-router tests pass (no test_design_prompt_* file exists anymore). If anything fails because of an import or symbol that was supposed to be deleted but is still referenced, fix the reference.

- [ ] **Step 5: Stage changes (no commit)**

```bash
git add backend/auth_service/models/schemas.py \
        backend/auth_service/routers/admin_leads.py
```

---

## Task 3: Cleanup — Worker + workflow

Remove the GH-Actions worker and its tests.

**Files:**
- Delete: `scripts/generate_design_prompt.py`
- Delete: `scripts/tests/__init__.py`
- Delete: `scripts/tests/test_generate_design_prompt.py`
- Delete: `.github/workflows/generate-design-prompt.yml`

- [ ] **Step 1: Delete all four files**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git rm -f scripts/generate_design_prompt.py \
          scripts/tests/__init__.py \
          scripts/tests/test_generate_design_prompt.py \
          .github/workflows/generate-design-prompt.yml
```

- [ ] **Step 2: Confirm `scripts/tests/` is now empty**

```bash
ls "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/scripts/tests/" 2>/dev/null
```

If the directory is empty, `git rm -f` already removed the tracked files but the dir may linger as an empty dir. Leave it; future work may use it.

If the dir DOES contain other files we don't know about, **stop and ask**.

- [ ] **Step 3: Stage (no commit)**

The `git rm` calls auto-staged. Confirm with:

```bash
git status --short | grep -E "scripts/|workflows/generate"
```

Expected: four `D ` (deleted) entries.

---

## Task 4: Cleanup — Frontend (delete + revert)

Remove the Tasks 9–12 additions.

**Files:**
- Delete: `frontend/src/components/admin/leads/hooks/useDesignPromptGenerations.ts`
- Delete: `frontend/src/components/admin/leads/hooks/__tests__/useDesignPromptGenerations.test.ts`
- Delete: `frontend/src/components/admin/leads/sections/GeneratedDesignPromptSection.tsx`
- Delete: `frontend/src/components/admin/leads/sections/__tests__/GeneratedDesignPromptSection.test.tsx`
- Revert: `frontend/src/components/admin/leads/types.ts`
- Revert: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`

- [ ] **Step 1: Delete the section + hook + their tests**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git rm -f frontend/src/components/admin/leads/hooks/useDesignPromptGenerations.ts \
          frontend/src/components/admin/leads/hooks/__tests__/useDesignPromptGenerations.test.ts \
          frontend/src/components/admin/leads/sections/GeneratedDesignPromptSection.tsx \
          frontend/src/components/admin/leads/sections/__tests__/GeneratedDesignPromptSection.test.tsx
```

- [ ] **Step 2: Revert `types.ts`**

Open `frontend/src/components/admin/leads/types.ts`. Remove the bottom section added in Task 9:

```ts
// ── Design-prompt generations ────────────────────────────────────────────

export type DesignPromptGenerationStatus = "pending" | "running" | "done" | "failed";

export interface DesignPromptGeneration {
  id: string;
  lead_id: string;
  status: DesignPromptGenerationStatus;
  result_xml: string | null;
  error_message: string | null;
  input_snapshot: Record<string, unknown>;
  triggered_by: string | null;
  model: string;
  skill_version: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface DesignPromptGenerationsResponse {
  items: DesignPromptGeneration[];
  total: number;
}
```

After deletion the file ends with `EMPTY_CONVERSION_FILTERS` (pre-Task-9 final line).

- [ ] **Step 3: Revert `LeadDetailDrawer.tsx`**

Open `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`. Delete:

a) The import (near top, around line 27):

```tsx
import { GeneratedDesignPromptSection } from "./sections/GeneratedDesignPromptSection";
```

b) The JSX line below `<DesignPromptSection lead={lead} onPatched={onPatched} />`:

```tsx
        <GeneratedDesignPromptSection leadId={lead.id} />
```

- [ ] **Step 4: Type-check the frontend**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/frontend" && npx tsc --noEmit
```

Expected: no errors. (The removed types/imports were only referenced inside files we also deleted — so no orphan references should remain.)

- [ ] **Step 5: Run the leads test suite (smoke)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/frontend" && npx vitest run src/components/admin/leads/
```

Expected: all remaining tests pass.

- [ ] **Step 6: Stage (no commit)**

```bash
git add frontend/src/components/admin/leads/types.ts \
        frontend/src/components/admin/leads/LeadDetailDrawer.tsx
```

(Deletions auto-staged by `git rm`.)

---

## Task 5: Cleanup — Docs (delete superseded spec + plan)

**Files:**
- Delete: `docs/superpowers/specs/2026-05-21-generate-design-prompt-design.md`
- Delete: `docs/superpowers/plans/2026-05-21-generate-design-prompt.md`

- [ ] **Step 1: Delete both docs**

These were never `git add`ed (they were untracked from the prior brainstorming session). Use plain `rm`:

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
rm -f docs/superpowers/specs/2026-05-21-generate-design-prompt-design.md \
      docs/superpowers/plans/2026-05-21-generate-design-prompt.md
```

- [ ] **Step 2: Verify no remaining references to those docs in the codebase**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
```

```bash
grep -r "2026-05-21-generate-design-prompt" --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yml" . 2>/dev/null | grep -v "docs/superpowers/specs/2026-05-21-design-prompt-creator-agent-design.md"
```

Expected: zero matches. (The new spec mentions Tasks 1–12 by general phrasing, never by filename of the deleted plan.)

- [ ] **Step 3: Stage (nothing to stage — they were untracked, deletion is invisible to git)**

Skip this step.

---

## Task 6: Build — Folder skeleton + empty seed files

Create the directory tree, empty research files, and the empty LEARNINGS.

**Files:**
- Create: `agents/Design Prompt creator/LEARNINGS.md`
- Create: `agents/Design Prompt creator/research/{restaurant,cafe,salon,venue,retail,service}.md` (6 files)
- Create: `agents/Design Prompt creator/feedback/pending/.gitkeep`
- Create: `agents/Design Prompt creator/feedback/archive/.gitkeep`
- Create: `agents/Design Prompt creator/runs/.gitkeep`

- [ ] **Step 1: Create the dir tree**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
mkdir -p "agents/Design Prompt creator/phases" \
         "agents/Design Prompt creator/research" \
         "agents/Design Prompt creator/feedback/pending" \
         "agents/Design Prompt creator/feedback/archive" \
         "agents/Design Prompt creator/runs"
```

- [ ] **Step 2: Create empty `LEARNINGS.md`**

Use Write to create `agents/Design Prompt creator/LEARNINGS.md` with this exact content:

```markdown
# Learnings — Design Prompt Creator

> Distilled lessons from feedback Stefan left after reviewing generated
> prompts. Auto-updated by Phase 2 of the agent. Each entry: short,
> sourced (date), generalisable. Per-lead specifics are dropped.

## General

(none yet)

## Category: restaurant

(none yet)

## Category: cafe

(none yet)

## Category: salon

(none yet)

## Category: venue

(none yet)

## Category: retail

(none yet)

## Category: service

(none yet)
```

- [ ] **Step 3: Create 6 empty research files with skeleton**

For each of `restaurant`, `cafe`, `salon`, `venue`, `retail`, `service`, create `agents/Design Prompt creator/research/<category>.md` with this exact content (substituting `<Category>` for the title-cased name):

```markdown
# Research — <Category>

**Last refreshed:** (never)

## Reference brands

(none yet — Phase 4 populates this on first run that meets the freshness rules)

## Common patterns observed

(regenerated by Phase 4 once ≥5 brands of one archetype exist)
```

For example, `restaurant.md`:

```markdown
# Research — Restaurant

**Last refreshed:** (never)

## Reference brands

(none yet — Phase 4 populates this on first run that meets the freshness rules)

## Common patterns observed

(regenerated by Phase 4 once ≥5 brands of one archetype exist)
```

Repeat for the other 5 categories with the title-cased name (`Cafe`, `Salon`, `Venue`, `Retail`, `Service`).

- [ ] **Step 4: Create `.gitkeep` files for empty dirs**

```bash
touch "agents/Design Prompt creator/feedback/pending/.gitkeep" \
      "agents/Design Prompt creator/feedback/archive/.gitkeep" \
      "agents/Design Prompt creator/runs/.gitkeep"
```

- [ ] **Step 5: Stage everything created (no commit)**

```bash
git add "agents/Design Prompt creator/LEARNINGS.md" \
        "agents/Design Prompt creator/research/" \
        "agents/Design Prompt creator/feedback/pending/.gitkeep" \
        "agents/Design Prompt creator/feedback/archive/.gitkeep" \
        "agents/Design Prompt creator/runs/.gitkeep"
```

---

## Task 7: Build — `AGENTS.md` (authoritative spec)

The single source of truth for what the agent does. Mirrors the format of `agents/Solver - Issues/AGENTS.md` and `agents/CMS Connector - Website/AGENTS.md`.

**Files:**
- Create: `agents/Design Prompt creator/AGENTS.md`

- [ ] **Step 1: Write the file**

Use Write to create `agents/Design Prompt creator/AGENTS.md` with this exact content:

````markdown
# Design Prompt Creator Agent

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/design-prompt-creator/SKILL.md`](../../.claude/skills/design-prompt-creator/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

> "Run Design Prompt Creator for lead `<lead_id>` [optional hints]"

Close paraphrases also match: *"Generate design prompt for lead X"*, *"Create design brief for X"*. The skill at `.claude/skills/design-prompt-creator/SKILL.md` enforces the trigger pattern.

Local-only. No remote triggering (no GitHub Actions, no cron). Stefan invokes from Claude Code in this repo.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|---|---|---|
| 0 | Parse intent | [phases/0-parse-intent.md](./phases/0-parse-intent.md) | Extract `lead_id` + mode flags from the trigger |
| 1 | Load lead | [phases/1-load-lead.md](./phases/1-load-lead.md) | Fetch + normalise + classify the lead |
| 2 | Consume feedback | [phases/2-consume-feedback.md](./phases/2-consume-feedback.md) | Distill `feedback/pending/*.md` into `LEARNINGS.md` |
| 3 | Check research | [phases/3-check-research.md](./phases/3-check-research.md) | Decide whether fresh research is needed |
| 4 | Research (conditional) | [phases/4-research.md](./phases/4-research.md) | WebSearch + WebFetch up to 4 sites, append to `research/<category>.md` |
| 5 | Generate | [phases/5-generate.md](./phases/5-generate.md) | Invoke `lead-to-design-prompt` skill with enriched context |
| 6 | Write back | [phases/6-writeback.md](./phases/6-writeback.md) | UPDATE `leads.design_prompt`, create feedback template |

## Constants

| Name | Value | Used by |
|---|---|---|
| `SUPABASE_PROJECT_ID` | `xeluydwpgiddbamysgyu` | Phases 1, 6 (every `mcp__supabase__execute_sql` call passes this) |
| `MAX_WEBSEARCH_QUERIES_PER_RUN` | 4 | Phase 4 |
| `MAX_WEBFETCH_URLS_PER_RUN` | 4 | Phase 4 |
| `WEBFETCH_BYTE_CAP` | 100 KB per URL | Phase 4 |
| `RESEARCH_STALENESS_DAYS` | 60 | Phase 3 |
| `RESEARCH_MIN_BRANDS_PER_CATEGORY` | 5 | Phase 3 |
| `RESEARCH_FORCE_ASK_THRESHOLD` | 10 brands | Phase 0 clarifying-question rule |

## Mode flags (parsed by Phase 0)

| Token in trigger | Effect |
|---|---|
| `force fresh research` | Phase 3 always says "research needed"; Phase 4 always runs |
| `skip research` / `cache only` | Phase 4 unconditionally skipped |
| `dry-run` | Phase 6 prints output, NO Supabase write, NO feedback template |
| `verbose` | Each phase echoes a 1-line summary of what it found |
| `reuse structure from lead <X>` | Phase 5 fetches lead X's `design_prompt` (strips wrapper) as extra reference |
| `style hint: <free text>` | Free-form aesthetic hint, threaded into Phase 5 context |

## Clarifying-question rules

The agent asks ONCE and waits when:

| Situation | Question |
|---|---|
| `lead_id` missing or ambiguous | "Which lead? Paste id." |
| Lead has no `business_name` or `category` | "Lead X is missing `category` — guess from description, or halt?" |
| `force fresh research` BUT cache already has ≥10 brands | "Cache for `<category>` already has N brands. Research more anyway, or use existing?" |
| Stefan's hint contradicts an anti-pattern (e.g., purple gradient) | "That choice is on the anti-slop ban list. Propose `<alternative>` in the same mood — OK?" |
| `reuse structure from lead <X>` but X has no `design_prompt` set | "Lead X has no `design_prompt`. Pick a different reference or proceed without?" |
| Phase 5 output has no fenced ` ```xml ` block | Show first 500 chars, ask retry / save-as-is / abort |

Routine choices (which archetype to pick, which sites to research, exact phrasing of copy seeds) are the agent's job — **never** ask Stefan about those.

## Tools the agent uses

- `Read`, `Edit`, `Write`, `Glob`, `Grep` — markdown + filesystem
- `WebSearch`, `WebFetch` — Phase 4 only
- `Skill` — to invoke `lead-to-design-prompt` (Phase 5)
- `mcp__supabase__execute_sql` — Phases 1 and 6, project_id `xeluydwpgiddbamysgyu`
- `Bash` — rare, mostly for `mv` archiving in Phase 2

The agent does **not** use the FastAPI backend. All Supabase access is direct via MCP.

## Self-improvement loop

Every run:
1. Phase 2 consumes pending feedback into `LEARNINGS.md`.
2. Phase 5 reads `LEARNINGS.md` + `research/<category>.md` and threads them as additional context into the `lead-to-design-prompt` skill call.
3. Phase 6 writes the result + creates a blank feedback template for this lead.

When Stefan reviews and adds notes to that template, the **next** run's Phase 2 picks them up — no manual "train the agent" command.

## Token rules

- Read phase docs lazily (one Read per phase, do not re-Read).
- Read LEARNINGS.md only after Phase 2 (Phase 2 itself reads + writes it).
- Read the relevant `research/<category>.md` once in Phase 3 (Phase 4 may re-edit it).
- No verbose narration — one status line per phase.
- Token budget target: 30K–80K per run. Hard cap: 150K — if approaching, skip the "Common patterns observed" regeneration in Phase 4.

## Failure modes (overview)

Each phase doc owns its own failure table. Cross-cutting rules:

- If `mcp__supabase__execute_sql` fails (Phase 1 SELECT) → halt + report exact error.
- If `mcp__supabase__execute_sql` fails (Phase 6 UPDATE) → save XML to `runs/<lead_id>_<datestamp>.xml`, report path, do not lose work.
- Phase 5 skill-invocation failures → ask Stefan (retry / save-as-is / abort).
- Phase 4 WebSearch / WebFetch failures → degrade gracefully, never halt the whole run.

## Out of scope (revisit later)

- Token cost / usage telemetry per run
- Slack notification when a run completes
- Bulk mode (run for N leads in one invocation)
- Per-city competitor research (second-tier cache)
- A frontend "Generate" button
````

- [ ] **Step 2: Stage (no commit)**

```bash
git add "agents/Design Prompt creator/AGENTS.md"
```

---

## Task 8: Build — `SKILL.md` (trigger entry)

The Claude Code skill that Stefan invokes. Following the format of `.claude/skills/cms-connector-website/SKILL.md`.

**Files:**
- Create: `.claude/skills/design-prompt-creator/SKILL.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/.claude/skills/design-prompt-creator"
```

- [ ] **Step 2: Write the SKILL.md**

Use Write to create `.claude/skills/design-prompt-creator/SKILL.md` with this exact content:

````markdown
---
name: design-prompt-creator
description: Use when the user says "Run Design Prompt Creator for lead <lead_id>" (or close paraphrase). Drives a 7-phase pipeline that researches the web for popular websites in the lead's category, invokes the lead-to-design-prompt skill with enriched context, and writes the resulting XML design prompt to leads.design_prompt via Supabase MCP. Self-learns via LEARNINGS.md (distilled feedback) and per-category research files.
---

# Design Prompt Creator (skill)

## Trigger pattern

Invoke this skill when the user message matches:

> "Run Design Prompt Creator for lead `<lead_id>` [optional hints]"

Close paraphrases match too: *"Generate design prompt for lead X"*, *"Create design brief for X"*, *"Design Prompt Creator on X"*.

If the trigger fires but `lead_id` is missing or unrecognisable, ask once for the lead id. Do not guess.

## First steps (always)

1. Read `agents/Design Prompt creator/AGENTS.md` — the workflow index + constants table.
2. Read `agents/Design Prompt creator/LEARNINGS.md` only if `wc -l` reports more than 25 lines (skip the empty scaffold to save tokens).
3. Confirm Supabase MCP is connected. The agent uses `mcp__supabase__execute_sql` with `project_id: xeluydwpgiddbamysgyu` (the `CMS` project).
4. Echo a one-line plan: *"Lead `<id>` · mode: `<flags or default>`. Phases 1–6 to follow."* Do not preview every phase.

## Lazy phase loading

Do **not** read all phase docs up front. As you enter each phase, read only that phase's file. After the phase succeeds, do not keep its content in active memory.

| Phase | When entering, Read |
|---|---|
| 0 | `agents/Design Prompt creator/phases/0-parse-intent.md` |
| 1 | `agents/Design Prompt creator/phases/1-load-lead.md` |
| 2 | `agents/Design Prompt creator/phases/2-consume-feedback.md` |
| 3 | `agents/Design Prompt creator/phases/3-check-research.md` |
| 4 | `agents/Design Prompt creator/phases/4-research.md` |
| 5 | `agents/Design Prompt creator/phases/5-generate.md` |
| 6 | `agents/Design Prompt creator/phases/6-writeback.md` |

## Token-optimization rules (binding)

- **One Read per phase doc** — do not re-Read the same phase file later in the run.
- **No verbose narration** — one status line per phase. No "Now I will..." prelude.
- **Tool output**: prefer `head_limit` and `offset` on Grep/Glob; never request full directory dumps.
- **Model policy** — defaults to whatever the user is running. No model-switching mid-run.
- **Skip the empty LEARNINGS.md** as noted above.

## Self-improvement loop

When Stefan leaves feedback in `agents/Design Prompt creator/feedback/pending/lead_<id>_*.md` after a run:

1. The NEXT run's Phase 2 picks up all pending files, distills lessons into `LEARNINGS.md`, archives the consumed files.
2. Subsequent phases use the updated `LEARNINGS.md` automatically.

The agent does NOT need an explicit "consume feedback" command. The loop runs whenever the agent runs.

## Failure mode hooks

- Halt on Supabase connect failure (Phase 1).
- Skip individual WebFetch failures (Phase 4); never halt the whole run on a single bad URL.
- On Phase 5 extraction failure, ask Stefan: retry / save-as-is / abort.
- On Phase 6 UPDATE failure, fall back to `agents/Design Prompt creator/runs/<lead_id>_<datestamp>.xml`.
````

- [ ] **Step 3: Stage (no commit)**

```bash
git add ".claude/skills/design-prompt-creator/SKILL.md"
```

---

## Task 9: Build — Phase 0 and Phase 1 docs

Two phases packed together because they're both about preparation (parse + load).

**Files:**
- Create: `agents/Design Prompt creator/phases/0-parse-intent.md`
- Create: `agents/Design Prompt creator/phases/1-load-lead.md`

- [ ] **Step 1: Write Phase 0 doc**

Use Write to create `agents/Design Prompt creator/phases/0-parse-intent.md`:

````markdown
# Phase 0 — Parse intent

**Goal:** Extract `lead_id` and mode flags from the user's trigger prompt. Surface clarifying questions before any work.

**Inputs:** the user message that invoked the skill.

## Steps

1. Find `lead_id` in the message. Accept any uuid-like string. If missing → ask: *"Which lead? Paste id."*  Halt if no answer.

2. Scan for mode flags (case-insensitive, free placement in the message):

   | Token | Sets |
   |---|---|
   | `force fresh research` / `force research` | `mode.force_research = true` |
   | `skip research` / `cache only` | `mode.skip_research = true` |
   | `dry-run` / `dry run` | `mode.dry_run = true` |
   | `verbose` | `mode.verbose = true` |
   | `reuse structure from lead <X>` | `mode.reuse_from_lead = <X>` |
   | `style hint: <free text up to end-of-line or 200 chars>` | `mode.style_hint = <text>` |

3. If both `force fresh research` AND `skip research` are set → ask: *"You set both `force` and `skip`. Pick one."* Halt if no answer.

4. Echo a one-line plan to chat:

   ```
   Lead <id> · mode: <flags-joined-by-comma, or "default">. Phases 1–6 to follow.
   ```

## Outputs

- `lead_id` (string, required)
- `mode` dict with the 6 fields above (defaults: all false / null)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `lead_id` missing | "Which lead? Paste id." |
| Contradictory flags | "You set both `force` and `skip` research. Pick one." |

## Self-improvement hook

If a free-form flag keeps appearing in triggers that the parser doesn't recognize (e.g., `--detailed`), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Recognise `<token>` as `<mapping>`. Triggered by: <short context>.`
````

- [ ] **Step 2: Write Phase 1 doc**

Use Write to create `agents/Design Prompt creator/phases/1-load-lead.md`:

````markdown
# Phase 1 — Load lead

**Goal:** Fetch the lead row, normalise it, classify into a category bucket, and prepare the skill-input payload.

**Inputs:** `lead_id` from Phase 0. Supabase MCP connection (project_id `xeluydwpgiddbamysgyu`).

## Steps

1. Call `mcp__supabase__execute_sql`:

   ```sql
   SELECT * FROM leads WHERE id = '<lead_id>';
   ```

   If the result is empty → halt + report: *"Lead `<lead_id>` not found."*

2. Normalise the row:

   - Replace any field where the value is literally `"Not found"`, `"N/A"`, or `"-"` with `null`.
   - Expand 2-letter country ISO codes: `NL` → `Netherlands`, `BE` → `Belgium`, `DE` → `Germany`. Other codes: pass through unchanged.
   - If `lat` OR `lng` is null, set BOTH to null (the skill drops the map embed only when both are absent).
   - **Strip `<pre><code>` wrapper from `design_prompt` if present:** look for `^\s*<pre><code>(.+?)</code></pre>\s*$` (DOTALL). If matched, replace with the captured content. If not matched, leave as-is.

3. Classify into one of the 6 category buckets (use `category` field; if ambiguous, infer from `description` + `extra.attributes`):

   - `restaurant` — restaurant, bistro, trattoria, brasserie, pizzeria, steakhouse, ramen, sushi, fine dining
   - `cafe` — cafe, coffee shop, bakery, patisserie, tea house, juice bar
   - `salon` — hair salon, barber, beauty salon, nail studio, spa, brow/lash studio
   - `venue` — wedding venue, event space, banquet hall, conference centre, ceremony location
   - `retail` — boutique, clothing store, gift shop, concept store, florist, jewellery
   - `service` — fallback for everything else

   If both `business_name` and `category` are empty/null → ask: *"Lead `<id>` has no `business_name` or `category`. Halt or guess from description?"*

4. Project the row to the **skill-input whitelist**:

   ```
   business_name, category, description, about, design_prompt,
   country, region, city, address, postal_code, lat, lng,
   phone, email, website_url, facebook_url, instagram_url,
   menu_url, web_presence, source_url,
   rating, review_count, reviews,
   opening_hours, extra, notes
   ```

   Plus inject `photo_urls` into `extra.photo_urls` if `photo_urls` is non-empty:

   ```python
   extra = dict(lead.get("extra") or {})
   if lead.get("photo_urls"):
       extra["photo_urls"] = lead["photo_urls"]
   projected["extra"] = extra
   ```

   (This logic happens in Claude's working memory; nothing is written to disk in Phase 1.)

5. If `mode.verbose` is set, echo: *"Phase 1: lead `<business_name>` (category bucket: `<bucket>`)."*

## Outputs

- `lead` — the projected, normalised lead JSON
- `category_bucket` — one of the 6 strings above
- `previous_design_prompt` — the stripped raw text (or null), for use in Phase 5 if iterating

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Lead not found | "Lead `<id>` not found in Supabase." |
| Both name + category missing | "Lead `<id>` has no `business_name` or `category`. Halt or guess from description?" |
| Supabase MCP error | "Supabase MCP call failed: `<error>`. Check MCP connection and re-run." |

## Self-improvement hook

If category classification keeps mis-bucketing a class of leads (e.g., "bistro" → restaurant when Stefan would prefer it bucketed as cafe), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Bucket "<term>" as <bucket>. Triggered by: feedback on lead <id>.`
````

- [ ] **Step 3: Stage (no commit)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git add "agents/Design Prompt creator/phases/0-parse-intent.md" \
        "agents/Design Prompt creator/phases/1-load-lead.md"
```

---

## Task 10: Build — Phase 2 and Phase 3 docs

State-preparation phases: feedback consumption + research-cache check.

**Files:**
- Create: `agents/Design Prompt creator/phases/2-consume-feedback.md`
- Create: `agents/Design Prompt creator/phases/3-check-research.md`

- [ ] **Step 1: Write Phase 2 doc**

Use Write to create `agents/Design Prompt creator/phases/2-consume-feedback.md`:

````markdown
# Phase 2 — Consume feedback

**Goal:** Read all pending feedback files, distill generalisable lessons into `LEARNINGS.md`, archive the consumed files.

**Inputs:** `category_bucket` from Phase 1. Filesystem.

## Steps

1. Glob `agents/Design Prompt creator/feedback/pending/*.md`.

2. If zero files found → echo *"Phase 2: no feedback pending."* and skip to Phase 3.

3. For each file (oldest mtime first):

   a. Read the file.

   b. Identify the *generalisable lesson*. Look at the section headed `## Generalisable lesson` if present. If that section is empty or the file is marked `## (optional) Discard if not generalisable`, drop the lesson but still archive the file.

   c. Determine which heading in `LEARNINGS.md` to write under:
      - If the lesson references a specific category (the per-lead file's lead is in a category, **and** the lesson talks about category-specific patterns), use `## Category: <bucket>`.
      - Else, use `## General`.

   d. Read `LEARNINGS.md`. Compare the new lesson to existing entries under the chosen heading:
      - If a near-duplicate exists, **strengthen** (rewrite the existing entry with combined wording + today's date).
      - If a contradiction exists (says the opposite), **replace** with the newer entry + note the date so the newer one wins.
      - Otherwise, **append** as a new bullet:
        ```
        - (<YYYY-MM-DD>) <lesson text>. Triggered by: lead <id>.
        ```

   e. Write the updated `LEARNINGS.md` back.

4. Move consumed files to `agents/Design Prompt creator/feedback/archive/<YYYY-MM>/<lead_id>.md`:

   ```bash
   mkdir -p "agents/Design Prompt creator/feedback/archive/<YYYY-MM>"
   mv "agents/Design Prompt creator/feedback/pending/<file>" \
      "agents/Design Prompt creator/feedback/archive/<YYYY-MM>/<lead_id>.md"
   ```

   (If a file with the same name already exists in archive — e.g., re-feedback for the same lead — append a timestamp: `<lead_id>_<HHMMSS>.md`.)

5. Echo: *"Phase 2: consumed N feedback files, updated LEARNINGS by M entries."*

## Outputs

- `LEARNINGS.md` (updated in place)
- `feedback/pending/` (drained)
- `feedback/archive/<YYYY-MM>/` (populated)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| File is unreadable / malformed | Skip that file, leave in `pending/`, warn: *"Phase 2: skipped `<file>` (unreadable). Will retry next run."* |
| `mv` fails | Skip the move, leave file in `pending/`, warn: *"Phase 2: could not archive `<file>` — left in pending."* |

## Self-improvement hook

If a feedback file keeps getting skipped because of malformed content, append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Reject feedback files without `## Generalisable lesson` heading. Triggered by: malformed file `<path>`.`
````

- [ ] **Step 2: Write Phase 3 doc**

Use Write to create `agents/Design Prompt creator/phases/3-check-research.md`:

````markdown
# Phase 3 — Check research cache

**Goal:** Decide whether Phase 4 needs to run by checking the per-category research file against three freshness signals.

**Inputs:** `category_bucket` from Phase 1. Mode flags from Phase 0.

## Steps

1. If `mode.skip_research` is set → set `research_needed = false`, echo *"Phase 3: research skipped (flag)."*  Skip to Phase 4 (which becomes a no-op).

2. If `mode.force_research` is set:
   - Read `research/<bucket>.md` and count brand entries (count `### ` headings under `## Reference brands`).
   - If count ≥ 10 (i.e., `RESEARCH_FORCE_ASK_THRESHOLD`) → ask: *"Cache for `<bucket>` already has N brands. Research more anyway, or use existing?"* If answer is "use existing", set `research_needed = false`. Otherwise `research_needed = true`.
   - If count < 10, set `research_needed = true` directly.

3. Otherwise (default mode): check three signals:

   a. **Staleness:** read `Last refreshed: <date>` from line 3 of `research/<bucket>.md`. If `(never)` → `stale = true`. If a real date older than `RESEARCH_STALENESS_DAYS = 60` days ago → `stale = true`. Else `stale = false`.

   b. **Coverage:** count `### ` brand entries under `## Reference brands`. If count < `RESEARCH_MIN_BRANDS_PER_CATEGORY = 5` → `under_covered = true`. Else `false`.

   c. **Archetype gap:** identify the lead's archetype from `category` + `description` + `extra.attributes`. Examples:
      - Restaurant: fine dining / casual / pizzeria / bistro / ethnic
      - Cafe: third-wave coffee / bakery / brunch / tea
      - Salon: hair / nails / spa / beauty
      - Venue: wedding / corporate / banquet
      - Retail: boutique / florist / gift / concept
      - Service: consulting / agency / trades / fitness

      Scan the brand entries' `**Type:**` field for a matching archetype label. If none of the brand entries match, `archetype_gap = true`.

   Set `research_needed = stale OR under_covered OR archetype_gap`.

4. Echo one line:

   ```
   Phase 3: research <needed | sufficient | overridden>. signals=stale:<bool>,coverage:<n>/5,archetype:<present|missing>.
   ```

## Outputs

- `research_needed` (boolean)
- Brand count, archetype, freshness flags — pass-through to Phase 4 so it doesn't re-read the file

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `research/<bucket>.md` doesn't exist (shouldn't happen — Task 6 seeds them) | Create from skeleton (Task 6 template), then proceed as if `(never)` refreshed. |

## Self-improvement hook

If Phase 3 keeps saying "sufficient" but Stefan repeatedly forces fresh research on the same category, append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Lower staleness threshold for `<bucket>` to 30 days. Triggered by: 3+ runs forced research after 30-50 day gaps.`
````

- [ ] **Step 3: Stage (no commit)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git add "agents/Design Prompt creator/phases/2-consume-feedback.md" \
        "agents/Design Prompt creator/phases/3-check-research.md"
```

---

## Task 11: Build — Phase 4 and Phase 5 docs

The two heavy phases: web research and skill invocation.

**Files:**
- Create: `agents/Design Prompt creator/phases/4-research.md`
- Create: `agents/Design Prompt creator/phases/5-generate.md`

- [ ] **Step 1: Write Phase 4 doc**

Use Write to create `agents/Design Prompt creator/phases/4-research.md`:

````markdown
# Phase 4 — Research (conditional)

**Goal:** Find 1–4 popular websites in the lead's category, extract structural design patterns, append to `research/<category>.md`.

**Inputs:** `category_bucket` and `research_needed` from Phase 3. Constraints from AGENTS.md (`MAX_WEBSEARCH_QUERIES_PER_RUN=4`, `MAX_WEBFETCH_URLS_PER_RUN=4`, `WEBFETCH_BYTE_CAP=100KB`).

## Steps

1. If `research_needed` is false → echo *"Phase 4: skipped (cache sufficient)."*  Skip to Phase 5.

2. Identify the lead's archetype (Phase 3 already did this — reuse) and the **gap** to fill. If the cache is missing fine-dining examples for restaurants, target that archetype. If under-covered overall, target the broadest popular examples.

3. WebSearch for popular sites. Cap: 4 queries total. Build queries like:

   - `popular minimalist <archetype> restaurant websites 2026`
   - `award-winning <category> website design`
   - `best <archetype> brand websites`
   - `<category> website inspiration 2026`

   Skip search results that:
   - Are listicles / blog posts ABOUT design (we want the actual sites)
   - Are clearly Wix / Squarespace template galleries (no design intent)
   - Are agency portfolios (the agency is the brand, not the SMB)

4. Select up to 4 distinct sites from the results (each query may yield candidates; deduplicate). Prefer sites that:
   - Have a clear distinctive aesthetic (not generic Bootstrap)
   - Match an archetype gap we're filling
   - Are reasonably recent (sites that look like 2018 trends are less useful)

5. For each selected site (cap: 4):

   a. WebFetch the URL with `byte_cap` 100 KB. If 100 KB cap is exceeded, take what you got.

   b. Extract these specific patterns from the page:
      - **Type:** archetype (one of the labels from Phase 3)
      - **Typography:** display font + body font (best guess from rendered CSS / visible text)
      - **Palette:** 2–4 dominant colours (best guess — name them: "cream", "forest green", "burgundy" etc.)
      - **Layout:** what's notable about the structure (asymmetric hero, editorial grid, full-bleed photography, etc.)
      - **Notable:** any structural choice worth borrowing (single-page vs multi, menu rendered as image, no online ordering, etc.)

   c. If WebFetch fails for that URL → skip silently, try next.

6. Append each new entry to `research/<bucket>.md` under `## Reference brands`:

   ```markdown
   ### <Brand Name> · <URL>
   - **Type:** <archetype>
   - **Typography:** <display + body>
   - **Palette:** <colours>
   - **Layout:** <notes>
   - **Notable:** <notes>
   - **Researched:** <YYYY-MM-DD>
   ```

7. Update line 3 of the file:

   ```
   **Last refreshed:** <YYYY-MM-DD>
   ```

8. If the file now has ≥5 brands of any single archetype, regenerate the `## Common patterns observed` section at the bottom:
   - Group brands by their `**Type:**` field
   - For each archetype with ≥5 brands, write 2–4 bullet observations
   - Replace the existing block (or create it if it was `(regenerated by Phase 4 once ≥5 brands of one archetype exist)`)

   If we're near the 150K-token cap on this run, skip step 8 — only append new brand entries.

9. Echo: *"Phase 4: researched N sites, appended to `research/<bucket>.md`."*

## Outputs

- `research/<bucket>.md` (updated)
- `research_content_for_phase_5` — the relevant excerpts (top 3–5 most relevant brand entries + Common patterns block) to thread into Phase 5

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| WebSearch returns nothing useful for any of the 4 queries | "Phase 4: web research found nothing actionable. Proceeding with existing cache." (continue) |
| All 4 WebFetches fail | "Phase 4: all 4 site fetches failed. Proceeding with existing cache." (continue) |
| Single WebFetch fails | Silently skip that URL, try next. |

## Self-improvement hook

If a category keeps returning low-quality search results (e.g., `service` is too broad), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: For `<bucket>` research, narrow query with `<sub-niche>` keyword. Triggered by: empty/low-quality results on N runs.`
````

- [ ] **Step 2: Write Phase 5 doc**

Use Write to create `agents/Design Prompt creator/phases/5-generate.md`:

````markdown
# Phase 5 — Generate

**Goal:** Invoke the existing `lead-to-design-prompt` skill with the lead JSON enriched with research insights + LEARNINGS lessons + Stefan's hints. Extract the fenced XML block from the skill's output.

**Inputs:** `lead` from Phase 1, `research_content_for_phase_5` from Phase 4 (may be empty if Phase 4 was skipped), `mode.style_hint` and `mode.reuse_from_lead` from Phase 0, current `LEARNINGS.md`.

## Steps

1. Build the additional-context block:

   ```markdown
   <additional_context>

   ## Research insights for this category

   <copy "Common patterns observed" block from research/<bucket>.md
    + 3-5 most relevant brand summaries — pick by archetype match
    with the lead's likely archetype>

   ## Lessons from prior runs

   <copy the "## General" section of LEARNINGS.md
    + the "## Category: <bucket>" section of LEARNINGS.md
    — verbatim, retain dates>

   ## Style hints from the trigger

   <if mode.style_hint is set, paste it here. Otherwise omit this section entirely.>

   ## Reference prompt to follow structure from

   <if mode.reuse_from_lead is set:
     1. Call mcp__supabase__execute_sql:
        SELECT design_prompt FROM leads WHERE id = '<reuse_from_lead>';
     2. If result is null/empty → ask: "Lead <X> has no design_prompt set. Pick a different reference, or proceed without?"
        - If "without", omit this section entirely.
        - If user picks another lead, retry with that one.
     3. If non-null:
        - Strip <pre><code>…</code></pre> wrapper if present (same regex as Phase 1).
        - Paste the raw stripped content here, fenced as ```xml … ```.
    Otherwise omit this section entirely.>

   </additional_context>
   ```

2. Build the prompt to send to the `Skill` tool (target: `lead-to-design-prompt`):

   ```
   Generate a design prompt for this lead:

   ```json
   <lead JSON from Phase 1, pretty-printed with indent=2>
   ```

   <additional_context block from step 1>
   ```

3. Invoke the skill via the `Skill` tool. The `lead-to-design-prompt` skill returns Markdown that includes one fenced ` ```xml ` code block.

4. Extract the first fenced ` ```xml ` block from the skill's output using regex:

   ```
   ```xml\n(.*?)\n```
   ```

   (DOTALL flag; first match wins.)

5. If extraction fails (no fenced xml block) → show the first 500 chars of the skill output and ask: *"The skill output has no ```xml block. Retry / save-as-is / abort?"*  Halt for answer.

6. Echo: *"Phase 5: generated `<N>` chars of XML."*

## Outputs

- `result_xml` — the extracted raw XML content

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Skill invocation fails | "Phase 5: lead-to-design-prompt skill failed: `<error>`. Retry?" Halt. |
| No fenced xml block in output | "Phase 5: model output has no `\`\`\`xml` block. First 500 chars: `<excerpt>`. Retry / save-as-is / abort?" Halt. |
| `reuse_from_lead` references a missing prompt | "Lead `<X>` has no `design_prompt`. Pick a different reference, or proceed without?" |

## Self-improvement hook

If Phase 5 keeps producing XML that Stefan then heavily edits (large diffs noted in feedback files), append to `LEARNINGS.md` under `## General` or the matching category section:
- `- <YYYY-MM-DD>: For `<context>`, the skill defaults to `<X>` but Stefan consistently prefers `<Y>`. Triggered by: feedback on N leads.`
````

- [ ] **Step 3: Stage (no commit)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git add "agents/Design Prompt creator/phases/4-research.md" \
        "agents/Design Prompt creator/phases/5-generate.md"
```

---

## Task 12: Build — Phase 6 doc

The write-back phase + feedback template creation.

**Files:**
- Create: `agents/Design Prompt creator/phases/6-writeback.md`

- [ ] **Step 1: Write Phase 6 doc**

Use Write to create `agents/Design Prompt creator/phases/6-writeback.md`:

````markdown
# Phase 6 — Write back

**Goal:** Persist the generated XML to `leads.design_prompt`. Create a blank feedback template so Stefan can leave lessons easily. Honor `dry-run` flag (no DB write, no template).

**Inputs:** `result_xml` from Phase 5, `lead_id` from Phase 0, `lead.business_name` from Phase 1, `mode.dry_run`.

## Steps

1. Wrap the XML in a HTML-safe envelope so the existing `DesignPromptSection` (TipTap, `dangerouslySetInnerHTML`) renders it as a code block:

   ```
   <pre><code><raw result_xml here, with & < > HTML-escaped></code></pre>
   ```

   HTML-escape rules:
   - `&` → `&amp;`
   - `<` → `&lt;`
   - `>` → `&gt;`

   (Do NOT escape inside the `<pre><code>` tags themselves — the escaping is for the XML body only.)

2. If `mode.dry_run` is set:
   - Print to chat:
     ```
     [dry-run] Would have UPDATEd leads.design_prompt for lead <id>:

     <wrapped XML, first 1000 chars + "…" if longer>

     [dry-run] Would have created agents/Design Prompt creator/feedback/pending/lead_<id>_<YYYY-MM-DD>.md
     ```
   - **Skip to step 5 (Echo).** No Supabase write, no feedback file.

3. Update Supabase via MCP:

   ```sql
   UPDATE leads
   SET design_prompt = $$<wrapped XML>$$
   WHERE id = '<lead_id>';
   ```

   (Use `$$…$$` dollar-quoting so the wrapped content's quotes/apostrophes don't need to be escaped inside the SQL string.)

   If the UPDATE returns 0 rows affected → halt + report *"Phase 6: UPDATE returned 0 rows. Lead `<id>` may have been deleted mid-run."*

   If the UPDATE fails (any other error) → fallback save:
   ```
   agents/Design Prompt creator/runs/<lead_id>_<YYYYMMDD_HHMMSS>.xml
   ```
   contains the raw XML (no `<pre><code>` wrapping). Report the path so Stefan can paste it manually.

4. Create the feedback template at `agents/Design Prompt creator/feedback/pending/lead_<lead_id>_<YYYY-MM-DD>.md`:

   ```markdown
   # Feedback — Lead <lead_id> (<business_name>)

   Generated: <YYYY-MM-DD HH:MM>

   ## What I changed before sending to Claude Design

   - (e.g., "Replaced the suggested Cormorant + Inter pair with Söhne + EB Garamond")

   ## Why

   - (e.g., "Inter is on our anti-slop list; Söhne fits the brief better")

   ## Generalisable lesson

   - (e.g., "Default away from Inter for boutique businesses even if 'modern'")

   ## (optional) Discard if not generalisable

   - Leave this section if the change was purely lead-specific
   ```

   If a file with the same name already exists (re-run on same date), append `_<HHMMSS>` to the filename: `lead_<lead_id>_<YYYY-MM-DD>_<HHMMSS>.md`.

5. Echo a final line to chat:

   ```
   ✓ Written to leads.design_prompt (length: <N> chars). Feedback template: agents/Design Prompt creator/feedback/pending/lead_<lead_id>_<YYYY-MM-DD>.md
   ```

## Outputs

- `leads.design_prompt` updated for `lead_id` (unless dry-run)
- `feedback/pending/lead_<id>_<date>.md` created (unless dry-run)
- OR `runs/<id>_<datestamp>.xml` written if Supabase failed

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Supabase UPDATE returns 0 rows | "Phase 6: UPDATE returned 0 rows. Lead `<id>` may have been deleted mid-run." |
| Supabase UPDATE fails | "Phase 6: UPDATE failed (`<error>`). Saved XML to `runs/<id>_<datestamp>.xml` — paste manually." |
| Feedback template create fails | "Phase 6: could not create feedback template at `<path>` (`<error>`). The DB write succeeded; you can leave feedback by manually creating the file." |

## Self-improvement hook

If the `<pre><code>` wrapping causes rendering issues in the dashboard (e.g., HTML entities double-escaped), append to `LEARNINGS.md` under `## General`:
- `- <YYYY-MM-DD>: Adjust wrapping/escaping in Phase 6 — current approach broke `<X>`. Triggered by: feedback on lead `<id>`.`
````

- [ ] **Step 2: Stage (no commit)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git add "agents/Design Prompt creator/phases/6-writeback.md"
```

---

## Task 13: Build — README + feedback README

Quick-reference docs.

**Files:**
- Create: `agents/Design Prompt creator/README.md`
- Create: `agents/Design Prompt creator/feedback/README.md`

- [ ] **Step 1: Write the agent README**

Use Write to create `agents/Design Prompt creator/README.md`:

````markdown
# Design Prompt Creator — quick reference

Local Claude-Code agent that turns one SMB lead into an XML design prompt for [claude.ai/design](https://claude.ai/design).

## How to use

In Claude Code, in this repo, type:

> "Run Design Prompt Creator for lead `<lead_id>`"

(`<lead_id>` is the uuid of a row in the `leads` table.)

Optional mode hints in the same message:

| Hint | Effect |
|---|---|
| `force fresh research` | Phase 4 always runs |
| `skip research` | Phase 4 unconditionally skipped |
| `dry-run` | Print the XML, don't write to DB |
| `verbose` | Each phase echoes a 1-line summary |
| `reuse structure from lead <X>` | Use lead X's existing prompt as a reference |
| `style hint: <free text>` | Add an aesthetic note to the skill invocation |

Examples:

- *"Run Design Prompt Creator for lead db28… verbose"*
- *"Generate design prompt for lead db28… force fresh research"*
- *"Create design brief for lead db28… style hint: like Aesop's restraint, dark palette"*
- *"Design Prompt Creator on db28… dry-run"*

## Files

- `AGENTS.md` — authoritative spec
- `LEARNINGS.md` — auto-grown lessons from your feedback
- `phases/0-parse-intent.md` — extract `lead_id` + mode flags
- `phases/1-load-lead.md` — fetch + classify lead
- `phases/2-consume-feedback.md` — distill feedback into LEARNINGS
- `phases/3-check-research.md` — decide if research is needed
- `phases/4-research.md` — WebSearch + WebFetch, append to research/
- `phases/5-generate.md` — invoke lead-to-design-prompt skill
- `phases/6-writeback.md` — UPDATE leads.design_prompt
- `research/<category>.md` — auto-grown reference library
- `feedback/pending/` — drop notes here per lead (see `feedback/README.md`)
- `feedback/archive/` — auto-moved here after Phase 2 consumes them
- `runs/` — fallback save target if Supabase write fails

## Self-improvement

Run completes → blank feedback template appears at `feedback/pending/lead_<id>_<date>.md`. Fill in lessons after you review the prompt. Next run automatically consumes it.

## Reset the cache

To force completely fresh research for a category:

```bash
echo "# Research — <Category>

**Last refreshed:** (never)

## Reference brands

(none yet — Phase 4 populates this on first run that meets the freshness rules)

## Common patterns observed

(regenerated by Phase 4 once ≥5 brands of one archetype exist)" > "research/<category>.md"
```

Or just delete the file — Phase 3 will recreate it from skeleton.
````

- [ ] **Step 2: Write the feedback README**

Use Write to create `agents/Design Prompt creator/feedback/README.md`:

````markdown
# Feedback — how it works

After every run, the agent creates a blank template in `pending/` for the lead it just processed. You edit it whenever you have something to say (no time limit — leave it for days if you want).

## Workflow

1. The agent emits `pending/lead_<id>_<date>.md` with this skeleton:

   ```markdown
   # Feedback — Lead <id> (<business_name>)

   Generated: <date>

   ## What I changed before sending to Claude Design

   - …

   ## Why

   - …

   ## Generalisable lesson

   - …

   ## (optional) Discard if not generalisable

   - Leave this section if the change was purely lead-specific
   ```

2. You review the prompt in the dashboard / claude.ai/design. If you edit anything before sending it to Claude Design, jot the change + the reason here.

3. **Most important section**: `## Generalisable lesson`. The agent's Phase 2 reads this on the next run and distills it into `LEARNINGS.md`. If the change was purely lead-specific (e.g., "lead is in Amsterdam, swapped the city name in copy"), leave the `## (optional) Discard if not generalisable` line — the agent will drop the lesson but still archive the file.

4. Next time you run the agent (any lead), Phase 2 picks up ALL pending files, updates `LEARNINGS.md`, and moves them to `archive/<YYYY-MM>/`.

## Tips for good lessons

- **Specific over vague.** "Default away from Inter for boutique cafes" beats "use better fonts".
- **Sourced.** The agent auto-adds the date + lead id when it copies your lesson into LEARNINGS.
- **One lesson per file.** If you have multiple unrelated lessons, edit the file to list each clearly so Phase 2 distills them as separate entries.
- **Skip the file** if you have nothing useful to say. Empty `## Generalisable lesson` + the discard line means Phase 2 archives without learning anything.
````

- [ ] **Step 3: Stage (no commit)**

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git add "agents/Design Prompt creator/README.md" \
        "agents/Design Prompt creator/feedback/README.md"
```

---

## Task 14: Manual smoke verification (Stefan-driven, not automated)

This is the only verification step. There are no tests in v1.

**Files:** none (verification only).

- [ ] **Step 1: Pick a known lead in Supabase with rich data**

In Supabase Studio (or via the dashboard), pick a lead that has: `business_name`, `category`, `description`, `rating` ≥ 4, `review_count` ≥ 5, `opening_hours`, and 2–3 photos. Copy its `id`.

- [ ] **Step 2: Open Claude Code in the repo, trigger the agent**

In a fresh Claude Code session:

> "Run Design Prompt Creator for lead `<id>` verbose"

Expected sequence (with `verbose` flag — each phase prints one line):

```
Lead <id> · mode: verbose. Phases 1–6 to follow.
Phase 1: lead <business_name> (category bucket: <bucket>).
Phase 2: no feedback pending.
Phase 3: research needed. signals=stale:true,coverage:0/5,archetype:missing.
Phase 4: researched 4 sites, appended to research/<bucket>.md.
Phase 5: generated <N> chars of XML.
✓ Written to leads.design_prompt (length: <N> chars). Feedback template: agents/Design Prompt creator/feedback/pending/lead_<id>_<date>.md
```

- [ ] **Step 3: Verify the four things**

a) **Supabase:** the row's `design_prompt` is non-null and starts with `<pre><code>` and contains XML inside. Use `mcp__supabase__execute_sql`:
   ```sql
   SELECT length(design_prompt), substring(design_prompt for 100) FROM leads WHERE id = '<id>';
   ```

b) **Research file:** `research/<bucket>.md` has 4 new brand entries under `## Reference brands` and `Last refreshed: <today>`.

c) **Feedback template:** the file `agents/Design Prompt creator/feedback/pending/lead_<id>_<date>.md` exists with the skeleton.

d) **Dashboard:** open the Lead Detail drawer for this lead in the dashboard at `http://localhost:3000` (backend + frontend running). The Design prompt section should now show the XML rendered as a code block (because of `<pre><code>` wrapping + TipTap's `dangerouslySetInnerHTML`).

- [ ] **Step 4: Test the dry-run flag**

Trigger again:

> "Run Design Prompt Creator for lead `<id>` dry-run"

Expected:
- Console prints the would-be XML + the would-be feedback path
- Supabase row UNCHANGED
- No new file in `feedback/pending/`

- [ ] **Step 5: Test the feedback loop**

a) Open `agents/Design Prompt creator/feedback/pending/lead_<id>_<date>.md` and fill in:

   ```markdown
   ## Generalisable lesson

   - (2026-05-21) For test leads, ensure typography section avoids Inter even when the lead is "modern".
   ```

b) Pick a different lead id from Supabase.

c) Trigger:

   > "Run Design Prompt Creator for lead `<different_id>` verbose"

   Expected:
   ```
   Phase 2: consumed 1 feedback files, updated LEARNINGS by 1 entries.
   ```

d) Inspect `agents/Design Prompt creator/LEARNINGS.md` — the lesson should be in `## General` (or `## Category: <bucket>` if it was category-specific).

e) Inspect `agents/Design Prompt creator/feedback/archive/<YYYY-MM>/lead_<id>.md` — the consumed file should be there.

f) Inspect `agents/Design Prompt creator/feedback/pending/` — should be empty (the consumed file moved) PLUS contain a new blank template for the new lead.

- [ ] **Step 6: Test `force fresh research`**

Trigger:

> "Run Design Prompt Creator for lead `<id>` force fresh research"

Expected: Phase 4 runs even though the cache now has brands from Step 2. The brand count grows.

- [ ] **Step 7: Commit when satisfied**

(Stefan only.) Once the agent works end-to-end:

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
git status
git commit -m "feat: Design Prompt Creator agent + cleanup of prior dashboard attempt"
git push -u origin feat/lead-scraper-system
```

---

## Self-Review

**Spec coverage:**

- §3 architecture (skill → AGENTS → phases 0–6 → MCP) → Tasks 7, 8, 9, 10, 11, 12. ✓
- §4 folder layout → Tasks 6, 7, 8, 13. ✓
- §5 trigger + intent parsing + clarifying questions → Task 8 (SKILL.md) + Task 9 (Phase 0). ✓
- §6 pipeline (0–6) → Tasks 9, 10, 11, 12. ✓
- §7 file formats (research, LEARNINGS, feedback template) → Tasks 6 (empty seeds), 12 (template emission in Phase 6 doc), 13 (feedback README). ✓
- §8 limits → encoded in AGENTS.md (Task 7) + Phase 4 doc (Task 11). ✓
- §9 cleanup (full revert of Tasks 1–12) → Tasks 1, 2, 3, 4, 5. ✓
- §10 self-improvement loop → Task 7 (AGENTS.md) + Task 10 (Phase 2 doc) + Task 13 (feedback README). ✓
- §11 file inventory → matches "File Structure" section above. ✓
- §12 skill input whitelist → Task 9 (Phase 1 doc). ✓
- §13 open questions → not implemented as code; remain in spec as flags for future. ✓
- §14 testing posture → Task 14 (manual smoke). ✓
- §15 out of scope → encoded in AGENTS.md (Task 7). ✓

**Placeholder scan:** no "TBD"/"TODO"/"implement later"/"similar to Task N" in the plan. Every step contains the actual content the implementer needs.

**Type/name consistency:**
- `lead_id`, `mode` keys (`force_research`, `skip_research`, `dry_run`, `verbose`, `reuse_from_lead`, `style_hint`), `category_bucket`, `research_needed`, `result_xml` — used consistently across Tasks 9–12.
- Path `agents/Design Prompt creator/` with literal spaces — same everywhere.
- `SUPABASE_PROJECT_ID = xeluydwpgiddbamysgyu` — same in Task 1 (apply_migration), Task 7 (AGENTS.md constants), Task 9 (Phase 1 doc), Task 12 (Phase 6 doc).
- Phase numbering: 0–6 (7 phases) throughout. Task 9 covers Phases 0+1, Task 10 covers 2+3, Task 11 covers 4+5, Task 12 covers 6. No phase missed, none duplicated.
- Wrapping format `<pre><code>…</code></pre>` referenced identically in Phase 1 (strip on read) and Phase 6 (apply on write).

No issues found.
