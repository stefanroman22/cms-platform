# CMS Preview & Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "See Preview" and "Publish Changes" buttons to the CMS. CMS edits flow into `draft_content`; Publish copies draft→published atomically; preview deployment reads drafts through a token-gated endpoint.

**Architecture:** Two-column draft/published split on `content_entries`. New endpoints for draft reads and project publish. Agent extended to auto-set-up Vercel (prod + `cms-preview` branch) and save URLs/tokens to the project row. Frontend adds a sticky `PreviewPublishBar` component on project overview + service editor pages.

**Tech Stack:** FastAPI (`backend/auth_service/`), Python 3, Supabase (Postgres), Next.js 15 App Router, TypeScript, Vitest, pytest, Vercel REST API, GitHub REST API.

**Spec:** `docs/superpowers/specs/2026-04-16-cms-preview-publish-design.md`

**Testing approach:** Unit tests mock the Supabase client (`get_supabase()`) to avoid requiring a real test project. Manual E2E (Task 19) covers the real integration.

---

## File Structure

### Created

| Path | Responsibility |
|---|---|
| `backend/auth_service/tests/__init__.py` | Empty marker |
| `backend/auth_service/tests/conftest.py` | Pytest fixtures (mock Supabase, mock auth, TestClient) |
| `backend/auth_service/tests/test_content.py` | Tests for `content.py` routes (public + draft) |
| `backend/auth_service/tests/test_workspace_save.py` | Tests for `save_service` draft-only write + `?seed=true` |
| `backend/auth_service/tests/test_publish.py` | Tests for `/publish`, `/status`, `/admin/rotate-preview-token` |
| `backend/auth_service/routers/publish.py` | New router: publish / status / rotate-token endpoints |
| `backend/agent/vercel.py` | Vercel REST API helpers (create project, set env vars, trigger deploy) |
| `backend/agent/github.py` | GitHub REST API helper (create `cms-preview` branch) |
| `backend/agent/tests/__init__.py` | Empty marker |
| `backend/agent/tests/test_vercel.py` | Tests for Vercel helpers (mocked HTTP) |
| `backend/agent/tests/test_github.py` | Tests for GitHub helper (mocked HTTP) |
| `backend/agent/tests/test_scan_vercel_phase.py` | Tests for the new `_vercel_setup` phase in scan.py |
| `frontend/src/components/dashboard/PreviewPublishBar.tsx` | Reusable bar component |
| `frontend/src/components/dashboard/PublishConfirmModal.tsx` | Confirm dialog for publish |
| `frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx` | Vitest coverage |
| `frontend/src/components/dashboard/__tests__/PublishConfirmModal.test.tsx` | Vitest coverage |
| `frontend/vitest.config.ts` | Only if not already present — verify first |

### Modified

| Path | Change |
|---|---|
| Supabase schema | Rename `content_entries.content` → `published_content`, add `draft_content`; add 6 columns on `projects`; add index |
| `backend/auth_service/routers/content.py` | Read `published_content`; filter null; add `/draft` endpoint |
| `backend/auth_service/routers/workspace.py` | `save_service` writes `draft_content` only; `_flatten_service` returns `draft ?? published`; `?seed=true` writes both; repeater seed writes both |
| `backend/auth_service/main.py` | Register `publish` router |
| `backend/auth_service/models/schemas.py` | Add `PublishResponse`, `ProjectStatusOut`, `RotateTokenResponse` |
| `backend/auth_service/requirements.txt` | Add `pytest`, `httpx` (TestClient dep), `pytest-asyncio` |
| `backend/agent/scan.py` | New CLI flags + `_vercel_setup()` phase call |
| `backend/agent/requirements.txt` | (Agent already uses stdlib HTTP — no new deps needed) |
| `frontend/src/app/dashboard/[projectSlug]/page.tsx` | Mount `<PreviewPublishBar projectSlug={projectSlug} />` at top |
| `frontend/src/app/dashboard/[projectSlug]/[serviceKey]/page.tsx` | Mount `<PreviewPublishBar projectSlug={projectSlug} />` at top |

---

## Task Order Rationale

1. **DB migration first** (Task 1) — everything after depends on the new schema.
2. **Test infra** (Task 2) — unblocks TDD.
3. **Content reads** (Tasks 3-4) — lowest-risk endpoint changes.
4. **Service writes** (Tasks 5-8) — change how CMS edits land in DB.
5. **Publish & status** (Tasks 9-12) — the user-facing verb.
6. **Agent Vercel integration** (Tasks 13-15) — onboarding, independent of UI.
7. **Frontend UI** (Tasks 16-18) — ties it all together.
8. **E2E smoke test** (Task 19) — validate the whole flow.

---

## Task 1: Database migration

**Files:**
- Apply via Supabase MCP (`mcp__supabase__apply_migration`)
- No test for this task (validated by later task tests)

- [ ] **Step 1: Verify Supabase project ID**

Run:
```
List Supabase projects via MCP to confirm which project to target.
```
Expected: one active project; record its ID.

- [ ] **Step 2: Apply the migration**

Use `mcp__supabase__apply_migration` with name `2026_04_16_draft_publish_split` and SQL:

```sql
-- Content entries: split into draft + published
ALTER TABLE content_entries RENAME COLUMN content TO published_content;
ALTER TABLE content_entries ADD COLUMN draft_content JSONB;

-- Backfill: every existing row's draft matches published (no pending changes)
UPDATE content_entries SET draft_content = published_content WHERE draft_content IS NULL;

-- Projects: Vercel + preview wiring
ALTER TABLE projects ADD COLUMN github_repo TEXT;
ALTER TABLE projects ADD COLUMN vercel_project_id TEXT;
ALTER TABLE projects ADD COLUMN production_url TEXT;
ALTER TABLE projects ADD COLUMN preview_url TEXT;
ALTER TABLE projects ADD COLUMN preview_token TEXT;
ALTER TABLE projects ADD COLUMN last_published_at TIMESTAMPTZ;

-- Index for "has unpublished changes" queries (used by /status endpoint)
CREATE INDEX idx_content_entries_needs_publish
  ON content_entries (project_service_id)
  WHERE published_content IS DISTINCT FROM draft_content;
```

- [ ] **Step 3: Verify migration applied**

Use `mcp__supabase__list_tables` and confirm:
- `content_entries` has `published_content` and `draft_content`, NOT `content`
- `projects` has the 6 new columns

Expected: all columns present.

- [ ] **Step 4: Commit**

No code change, but record the migration in the repo for history.

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
mkdir -p backend/migrations
cat > backend/migrations/2026_04_16_draft_publish_split.sql <<'EOF'
-- Applied 2026-04-16 via Supabase MCP
-- (content of the migration above)
EOF
# Paste exact SQL from Step 2 into the file
git add backend/migrations/2026_04_16_draft_publish_split.sql
git commit -m "db: split content into draft_content + published_content, add Vercel fields on projects"
```

---

## Task 2: Pytest infrastructure for backend

**Files:**
- Create: `backend/auth_service/tests/__init__.py`
- Create: `backend/auth_service/tests/conftest.py`
- Modify: `backend/auth_service/requirements.txt`
- Create: `backend/auth_service/pytest.ini`

- [ ] **Step 1: Add test dependencies**

Edit `backend/auth_service/requirements.txt` — append:

```
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.28.1
```

- [ ] **Step 2: Install**

Run: `cd "backend" && source venv/Scripts/activate && pip install -r auth_service/requirements.txt`
Expected: pytest + httpx installed.

- [ ] **Step 3: Create pytest.ini**

`backend/auth_service/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Create tests package marker**

`backend/auth_service/tests/__init__.py`: empty file.

- [ ] **Step 5: Create conftest.py with fixtures**

`backend/auth_service/tests/conftest.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from ..main import app
from ..models.schemas import UserOut


@pytest.fixture
def mock_supabase():
    """Patches get_supabase() everywhere it's imported.

    The returned MagicMock mimics the chained supabase-py builder; individual
    tests override .execute() return values per-call.
    """
    mock = MagicMock()
    # Make every builder method return the mock itself so chains like
    # .table().select().eq().single().execute() all work.
    for method in ["table", "select", "eq", "order", "limit", "single", "insert",
                   "upsert", "update", "delete", "neq", "filter"]:
        getattr(mock, method).return_value = mock

    # Each patch wrapped in try/except so early tasks can run before later
    # modules (e.g. publish.py in Task 7) exist.
    targets = [
        "auth_service.routers.content.get_supabase",
        "auth_service.routers.workspace.get_supabase",
        "auth_service.routers.projects.get_supabase",
        "auth_service.routers.publish.get_supabase",  # created in Task 7
    ]
    started = []
    for target in targets:
        try:
            p = patch(target, return_value=mock)
            p.start()
            started.append(p)
        except (ModuleNotFoundError, AttributeError):
            continue
    yield mock
    for p in started:
        p.stop()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user():
    return UserOut(id="admin-uuid", email="admin@example.com", full_name="Admin", is_admin=True)


@pytest.fixture
def client_user():
    return UserOut(id="client-uuid", email="laurian@example.com", full_name="Laurian", is_admin=False)


@pytest.fixture
def auth_as(monkeypatch):
    """Call `auth_as(user)` inside a test to bypass cookie auth with the given user."""
    def _apply(user: UserOut):
        async def fake_require_user(request):
            return user
        # Patch every router's require_user import site
        monkeypatch.setattr("auth_service.routers.workspace.require_user", fake_require_user)
        monkeypatch.setattr("auth_service.routers.projects.require_user", fake_require_user)
        # publish.py — added in Task 9, but the patch is idempotent (AttributeError caught)
        try:
            monkeypatch.setattr("auth_service.routers.publish.require_user", fake_require_user)
        except (AttributeError, ModuleNotFoundError):
            pass

        def fake_require_project_access(slug, u):
            return {"id": f"project-{slug}", "slug": slug, "name": slug.title()}
        monkeypatch.setattr("auth_service.routers.workspace.require_project_access", fake_require_project_access)
        try:
            monkeypatch.setattr("auth_service.routers.publish.require_project_access", fake_require_project_access)
        except (AttributeError, ModuleNotFoundError):
            pass
    return _apply
```

- [ ] **Step 6: Verify harness runs**

Run: `cd "backend" && python -m pytest auth_service/tests/ -v`
Expected: `no tests ran` (collection succeeds, no test files yet).

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/tests/ backend/auth_service/pytest.ini backend/auth_service/requirements.txt
git commit -m "test: add pytest infrastructure + Supabase mock fixtures for auth_service"
```

---

## Task 3: Public content endpoint reads `published_content` and filters nulls

**Files:**
- Modify: `backend/auth_service/routers/content.py:53-116`
- Test: `backend/auth_service/tests/test_content.py` (create)

- [ ] **Step 1: Write the failing test**

`backend/auth_service/tests/test_content.py`:

```python
def test_public_content_returns_published_content_only(mock_supabase, client):
    # Arrange — supabase returns one project + two services
    mock_supabase.execute.side_effect = [
        # _resolve_project
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        # services query
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {"title": "DRAFT"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    body = res.json()
    assert body["content"]["hero"]["title"] == "PUB"  # published, not draft


def test_public_content_filters_services_with_null_published(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(data=[
            {
                "service_key": "published_svc",
                "label": "Has published",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "YES"}, "draft_content": {"title": "D"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
            {
                "service_key": "unpublished_svc",
                "label": "Draft only",
                "display_order": 2,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": None, "draft_content": {"title": "D"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    content = res.json()["content"]
    assert "published_svc" in content
    assert "unpublished_svc" not in content
```

Add imports at top:
```python
from unittest.mock import MagicMock
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "backend" && python -m pytest auth_service/tests/test_content.py -v`
Expected: FAIL — current code reads `content` key, not `published_content`; doesn't filter nulls.

- [ ] **Step 3: Update content.py**

In `backend/auth_service/routers/content.py`:

**Replace the select string on line 60** — change:
```python
.select("service_key, label, display_order, service_type_slug, content_entries(content, updated_at)")
```
to:
```python
.select("service_key, label, display_order, service_type_slug, content_entries(published_content, draft_content, updated_at)")
```

**Replace line 74** — change:
```python
raw_content: dict = entry.get("content", {}) if entry else {}
```
to:
```python
raw_published: dict | None = entry.get("published_content") if entry else None
# Filter: services with no published content don't appear in the public response.
if raw_published is None:
    continue
```

**Replace the `**raw_content` usage on line 83** with `**raw_published`:

```python
content_map[svc["service_key"]] = {
    "_type": svc["service_type_slug"],
    "_label": svc.get("label") or svc["service_key"],
    **raw_published,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/test_content.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/content.py backend/auth_service/tests/test_content.py
git commit -m "feat(content): read published_content and filter unpublished services from public endpoint"
```

---

## Task 4: Draft content endpoint

**Files:**
- Modify: `backend/auth_service/routers/content.py` (add new endpoint after line 116)
- Test: `backend/auth_service/tests/test_content.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/auth_service/tests/test_content.py`:

```python
def test_draft_endpoint_requires_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}
    )
    res = client.get("/content/demo/draft")
    assert res.status_code == 401


def test_draft_endpoint_rejects_wrong_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}
    )
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "wrong"})
    assert res.status_code == 401


def test_draft_endpoint_returns_draft_with_valid_token(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}),
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {"title": "DRAFT"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "DRAFT"
    assert res.headers["cache-control"] == "no-store"


def test_draft_falls_back_to_published_when_draft_null(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}),
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": None, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "PUB"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "backend" && python -m pytest auth_service/tests/test_content.py -v`
Expected: four new tests FAIL with 404 (endpoint doesn't exist).

- [ ] **Step 3: Update `_resolve_project` to include `preview_token`**

In `backend/auth_service/routers/content.py:27-39`, change the `.select()` to include `preview_token`:

```python
def _resolve_project(project_slug: str) -> dict:
    sb = get_supabase()
    result = (
        sb.table("projects")
        .select("id, name, slug, is_active, preview_token")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result.data
```

- [ ] **Step 4: Add the draft endpoint**

Append to `backend/auth_service/routers/content.py` (after `get_project_content`, before `get_project_types`):

```python
@router.get("/{project_slug}/draft")
async def get_project_draft_content(project_slug: str, request: Request):
    """Draft content for preview deployments. Requires X-CMS-Preview-Token header."""
    project = _resolve_project(project_slug)

    token_header = request.headers.get("X-CMS-Preview-Token")
    expected = project.get("preview_token")
    if not expected or token_header != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing preview token")

    sb = get_supabase()
    services_result = (
        sb.table("project_services")
        .select("service_key, label, display_order, service_type_slug, content_entries(published_content, draft_content, updated_at)")
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    content_map: dict = {}
    last_updated: str | None = None

    for svc in (services_result.data or []):
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue

        entry = _resolve_content_entry(svc)
        if entry is None:
            continue

        # Draft with fallback to published
        raw = entry.get("draft_content") or entry.get("published_content")
        if raw is None:
            continue

        updated_at: str | None = entry.get("updated_at")
        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at

        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **raw,
        }

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "last_updated": last_updated,
        "content": content_map,
    }

    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        },
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/test_content.py -v`
Expected: all six tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/content.py backend/auth_service/tests/test_content.py
git commit -m "feat(content): add /content/{slug}/draft endpoint gated by per-project preview token"
```

---

## Task 5: `save_service` writes `draft_content` only; `_flatten_service` returns draft-with-fallback

**Files:**
- Modify: `backend/auth_service/routers/workspace.py:66-92, 117-171, 281-308`
- Test: `backend/auth_service/tests/test_workspace_save.py` (create)

- [ ] **Step 1: Write failing tests**

`backend/auth_service/tests/test_workspace_save.py`:

```python
from unittest.mock import MagicMock


def test_put_service_writes_to_draft_content_only(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    # Sequence: _resolve, upsert, get_service's resolve + fetch
    mock_supabase.execute.side_effect = [
        # svc_result in save_service
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        }),
        # upsert returns
        MagicMock(data=[{"id": "svc-1"}]),
        # get_service re-fetch
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            "content_entries": {"published_content": {"title": "OLD"}, "draft_content": {"title": "NEW"}, "updated_at": "2026-04-16T10:00:00Z"},
        }),
    ]

    res = client.put(
        "/projects/demo/services/hero",
        json={"content": {"title": "NEW"}},
    )
    assert res.status_code == 200

    # Verify the upsert payload targeted draft_content, NOT published_content
    upsert_calls = [c for c in mock_supabase.upsert.call_args_list]
    assert any("draft_content" in c.args[0] for c in upsert_calls)
    assert not any("published_content" in c.args[0] for c in upsert_calls)


def test_get_service_returns_draft_with_fallback_to_published(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(data={
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {"title": "DRAFT"}, "updated_at": "2026-04-16T10:00:00Z"},
    })

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "DRAFT"


def test_get_service_falls_back_to_published_when_draft_null(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(data={
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": {"published_content": {"title": "PUB"}, "draft_content": None, "updated_at": "2026-04-16T10:00:00Z"},
    })

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "PUB"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "backend" && python -m pytest auth_service/tests/test_workspace_save.py -v`
Expected: FAIL (current code writes `content`, reads `content`).

- [ ] **Step 3: Update `_flatten_service`**

In `backend/auth_service/routers/workspace.py:66-92`, replace the function with:

```python
def _flatten_service(svc: dict) -> dict:
    """Extracts nested service_types + content_entries into a flat dict.

    `content` in the response is the draft (what the client is editing) — falls
    back to published_content if the service has never had a draft. Unpublished
    services with null published_content still return their draft to the CMS UI.
    """
    st = svc.get("service_types") or {}
    raw = svc.get("content_entries")
    if isinstance(raw, dict):
        entry = raw
    elif isinstance(raw, list):
        entry = raw[0] if raw else None
    else:
        entry = None

    draft = entry.get("draft_content") if entry else None
    published = entry.get("published_content") if entry else None
    content = draft if draft is not None else (published or {})

    return {
        "id": svc["id"],
        "service_key": svc["service_key"],
        "label": svc.get("label"),
        "service_type_slug": svc["service_type_slug"],
        "service_type_name": st.get("name", svc["service_type_slug"]),
        "service_type_icon": st.get("icon", "Box"),
        "display_order": svc.get("display_order", 0),
        "page_name": svc.get("page_name", "General"),
        "last_updated": entry.get("updated_at") if entry else None,
        "schema": st.get("schema", {}),
        "content": content,
    }
```

- [ ] **Step 4: Update `list_services` and `get_service` queries**

In `workspace.py:106`, change:
```python
.select("id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon), content_entries(updated_at)")
```
to:
```python
.select("id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon), content_entries(updated_at, draft_content, published_content)")
```

In `workspace.py:125`, change:
```python
.select("id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema), content_entries(content, updated_at)")
```
to:
```python
.select("id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema), content_entries(draft_content, published_content, updated_at)")
```

- [ ] **Step 5: Update `save_service` to write `draft_content` only**

In `workspace.py:159-168`, replace the upsert with:

```python
    # Upsert draft only — production keeps serving published_content until publish.
    sb.table("content_entries").upsert(
        {
            "project_service_id": svc_id,
            "draft_content": body.content,
            "updated_at": now,
            "updated_by": user.id,
        },
        on_conflict="project_service_id",
    ).execute()
```

- [ ] **Step 6: Update repeater seed in `add_service`**

In `workspace.py:302-307`, change the insert — seed BOTH columns (new service = draft matches published):

```python
            sb.table("content_entries").insert({
                "project_service_id": svc_result.data["id"],
                "published_content": {"_schema": schema_payload, "items": []},
                "draft_content": {"_schema": schema_payload, "items": []},
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": user.id,
            }).execute()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/ -v`
Expected: all tests (including Task 3-4) PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_save.py
git commit -m "feat(workspace): save to draft_content; service detail returns draft-with-published-fallback"
```

---

## Task 6: Agent `?seed=true` query param on PUT service — writes both columns

**Files:**
- Modify: `backend/auth_service/routers/workspace.py:137-171`
- Test: `backend/auth_service/tests/test_workspace_save.py`

- [ ] **Step 1: Write failing test**

Append to `test_workspace_save.py`:

```python
def test_put_service_with_seed_true_writes_both_columns(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)

    mock_supabase.execute.side_effect = [
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        }),
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            "content_entries": {"published_content": {"title": "X"}, "draft_content": {"title": "X"}, "updated_at": "2026-04-16T10:00:00Z"},
        }),
    ]

    res = client.put(
        "/projects/demo/services/hero?seed=true",
        json={"content": {"title": "X"}},
    )
    assert res.status_code == 200

    payload = mock_supabase.upsert.call_args_list[0].args[0]
    assert payload.get("draft_content") == {"title": "X"}
    assert payload.get("published_content") == {"title": "X"}


def test_put_service_seed_true_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    res = client.put(
        "/projects/demo/services/hero?seed=true",
        json={"content": {"title": "X"}},
    )
    assert res.status_code == 403
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd "backend" && python -m pytest auth_service/tests/test_workspace_save.py::test_put_service_with_seed_true_writes_both_columns -v`
Expected: FAIL (query param is ignored).

- [ ] **Step 3: Update `save_service` signature + body**

In `workspace.py:137-171`, modify the function to:

```python
@router.put("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def save_service(
    project_slug: str,
    service_key: str,
    body: ContentSaveRequest,
    request: Request,
    seed: bool = False,
):
    user = await require_user(request)
    if seed and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="seed=true requires admin")
    project = require_project_access(project_slug, user)

    sb = get_supabase()

    svc_result = (
        sb.table("project_services")
        .select("id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema)")
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not svc_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    svc_id = svc_result.data["id"]
    now = datetime.now(timezone.utc).isoformat()

    payload: dict = {
        "project_service_id": svc_id,
        "draft_content": body.content,
        "updated_at": now,
        "updated_by": user.id,
    }
    if seed:
        payload["published_content"] = body.content

    sb.table("content_entries").upsert(payload, on_conflict="project_service_id").execute()

    return await get_service(project_slug, service_key, request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/test_workspace_save.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_save.py
git commit -m "feat(workspace): admin-only ?seed=true flag on PUT service to initialize both draft+published"
```

---

## Task 7: `/projects/{slug}/publish` endpoint + `/status`

**Files:**
- Create: `backend/auth_service/routers/publish.py`
- Modify: `backend/auth_service/models/schemas.py`
- Modify: `backend/auth_service/main.py`
- Test: `backend/auth_service/tests/test_publish.py` (create)

- [ ] **Step 1: Add Pydantic schemas**

Append to `backend/auth_service/models/schemas.py`:

```python
# ── Preview / Publish ────────────────────────────────────────────────────────

class PublishResponse(BaseModel):
    published_count: int
    last_published_at: str | None


class ProjectStatusOut(BaseModel):
    unpublished_count: int
    last_published_at: str | None
    preview_url: str | None
    production_url: str | None


class RotateTokenResponse(BaseModel):
    preview_token: str
```

- [ ] **Step 2: Write failing tests**

`backend/auth_service/tests/test_publish.py`:

```python
from unittest.mock import MagicMock


def test_publish_copies_draft_to_published_and_bumps_timestamp(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    # Supabase mock for the RPC-like execute chain
    mock_supabase.execute.side_effect = [
        # Fetch project_services for this project
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}]),
        # Fetch entries that differ (our "needs publish" query)
        MagicMock(data=[
            {"project_service_id": "svc-1", "draft_content": {"title": "A"}},
            {"project_service_id": "svc-2", "draft_content": {"title": "B"}},
        ]),
        # Update entry 1
        MagicMock(data=[{"project_service_id": "svc-1"}]),
        # Update entry 2
        MagicMock(data=[{"project_service_id": "svc-2"}]),
        # Update projects.last_published_at
        MagicMock(data=[{"last_published_at": "2026-04-16T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    body = res.json()
    assert body["published_count"] == 2
    assert body["last_published_at"] is not None


def test_publish_with_no_changes_returns_zero(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(data=[]),  # no entries differ
        MagicMock(data=[{"last_published_at": "2026-04-16T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    assert res.json()["published_count"] == 0


def test_status_reports_unpublished_count_and_urls(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.side_effect = [
        # Fetch project fields
        MagicMock(data={
            "id": "project-demo",
            "preview_url": "https://preview.example.com",
            "production_url": "https://prod.example.com",
            "last_published_at": "2026-04-16T10:00:00Z",
        }),
        # Fetch project_services
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}, {"id": "svc-3"}]),
        # Count entries where draft != published
        MagicMock(data=[
            {"project_service_id": "svc-1"},
            {"project_service_id": "svc-3"},
        ]),
    ]

    res = client.get("/projects/demo/status")
    assert res.status_code == 200
    body = res.json()
    assert body["unpublished_count"] == 2
    assert body["preview_url"] == "https://preview.example.com"
    assert body["production_url"] == "https://prod.example.com"
    assert body["last_published_at"] == "2026-04-16T10:00:00Z"
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd "backend" && python -m pytest auth_service/tests/test_publish.py -v`
Expected: FAIL with 404 (router not registered).

- [ ] **Step 4: Create the publish router**

`backend/auth_service/routers/publish.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import ProjectStatusOut, PublishResponse
from ..services.supabase_client import get_supabase
from .deps import require_project_access, require_user

router = APIRouter(tags=["publish"])


@router.post("/projects/{project_slug}/publish", response_model=PublishResponse)
async def publish_project(project_slug: str, request: Request):
    """Atomically promotes draft_content → published_content for every service
    in the project where they differ. Bumps projects.last_published_at.
    """
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()

    # Resolve service IDs for this project
    svc_result = (
        sb.table("project_services")
        .select("id")
        .eq("project_id", project["id"])
        .execute()
    )
    svc_ids = [s["id"] for s in (svc_result.data or [])]
    if not svc_ids:
        return {"published_count": 0, "last_published_at": None}

    # Identify entries that need publishing (draft_content set AND differs from published)
    # supabase-py doesn't support IS DISTINCT FROM, so we fetch candidates and compare in Python.
    entries_result = (
        sb.table("content_entries")
        .select("project_service_id, draft_content, published_content")
        .in_("project_service_id", svc_ids)
        .execute()
    )

    to_publish = [
        e for e in (entries_result.data or [])
        if e.get("draft_content") != e.get("published_content")
    ]

    # Per-row update (supabase-py has no bulk-update-from-column-value; loop is fine for typical <50 services)
    now = datetime.now(timezone.utc).isoformat()
    for entry in to_publish:
        sb.table("content_entries").update({
            "published_content": entry["draft_content"],
            "updated_at": now,
        }).eq("project_service_id", entry["project_service_id"]).execute()

    # Bump project timestamp
    upd = (
        sb.table("projects")
        .update({"last_published_at": now})
        .eq("id", project["id"])
        .execute()
    )
    last_published_at = now

    return {"published_count": len(to_publish), "last_published_at": last_published_at}


@router.get("/projects/{project_slug}/status", response_model=ProjectStatusOut)
async def project_status(project_slug: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()

    # Fetch URLs + last_published_at
    p_result = (
        sb.table("projects")
        .select("id, preview_url, production_url, last_published_at")
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    p_data = p_result.data or {}

    # Count entries where draft != published
    svc_result = (
        sb.table("project_services")
        .select("id")
        .eq("project_id", project["id"])
        .execute()
    )
    svc_ids = [s["id"] for s in (svc_result.data or [])]
    unpublished_count = 0
    if svc_ids:
        entries_result = (
            sb.table("content_entries")
            .select("project_service_id, draft_content, published_content")
            .in_("project_service_id", svc_ids)
            .execute()
        )
        unpublished_count = sum(
            1 for e in (entries_result.data or [])
            if e.get("draft_content") != e.get("published_content")
        )

    return {
        "unpublished_count": unpublished_count,
        "last_published_at": p_data.get("last_published_at"),
        "preview_url": p_data.get("preview_url"),
        "production_url": p_data.get("production_url"),
    }
```

- [ ] **Step 5: Register router in main.py**

Edit `backend/auth_service/main.py` — change line 8:
```python
from .routers import auth, projects, content, workspace
```
to:
```python
from .routers import auth, projects, content, workspace, publish
```

Add after line 44 (after `app.include_router(issues_router)`):
```python
app.include_router(publish.router)
```

- [ ] **Step 6: Update conftest mock_supabase**

In `backend/auth_service/tests/conftest.py`, add `"in_"` to the list of chained methods (line with `["table", "select", ...]`), so `.in_()` returns the mock. Also add a patch for `publish`:

In `mock_supabase` fixture, change the methods list to include `in_`:
```python
for method in ["table", "select", "eq", "in_", "order", "limit", "single", "insert",
               "upsert", "update", "delete", "neq", "filter"]:
```

Add patch:
```python
patches = [
    patch("auth_service.routers.content.get_supabase", return_value=mock),
    patch("auth_service.routers.workspace.get_supabase", return_value=mock),
    patch("auth_service.routers.projects.get_supabase", return_value=mock),
    patch("auth_service.routers.publish.get_supabase", return_value=mock),
]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/test_publish.py -v`
Expected: all three tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/auth_service/routers/publish.py backend/auth_service/main.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_publish.py backend/auth_service/tests/conftest.py
git commit -m "feat(publish): add POST /projects/{slug}/publish + GET /projects/{slug}/status"
```

---

## Task 8: Admin rotate-preview-token endpoint (with Vercel env var update)

**Files:**
- Modify: `backend/auth_service/routers/publish.py`
- Test: `backend/auth_service/tests/test_publish.py`

- [ ] **Step 1: Write failing test**

Append to `test_publish.py`:

```python
from unittest.mock import patch as patch_


def test_rotate_preview_token_regenerates_and_stores(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)

    mock_supabase.execute.side_effect = [
        # Fetch project + vercel_project_id
        MagicMock(data={"id": "project-demo", "vercel_project_id": "prj_123"}),
        # Update row
        MagicMock(data=[{"preview_token": "<new>"}]),
    ]

    # Patch Vercel call to a no-op
    with patch_("auth_service.routers.publish._update_vercel_preview_env_var") as mock_vercel:
        res = client.post("/admin/projects/demo/rotate-preview-token")

    assert res.status_code == 200
    body = res.json()
    assert len(body["preview_token"]) >= 32
    mock_vercel.assert_called_once()


def test_rotate_preview_token_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    res = client.post("/admin/projects/demo/rotate-preview-token")
    assert res.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "backend" && python -m pytest auth_service/tests/test_publish.py::test_rotate_preview_token_regenerates_and_stores -v`
Expected: FAIL with 404 (endpoint doesn't exist).

- [ ] **Step 3: Implement endpoint**

Append to `backend/auth_service/routers/publish.py`:

```python
import os
import secrets
import urllib.error
import urllib.request
import json

from ..models.schemas import RotateTokenResponse


VERCEL_API_BASE = "https://api.vercel.com"


def _update_vercel_preview_env_var(vercel_project_id: str, new_token: str) -> None:
    """Updates CMS_PREVIEW_TOKEN env var on the Vercel project's Preview environment.

    Uses VERCEL_TOKEN from the server environment. If unset, skip silently —
    the DB token is still rotated and a re-deploy of the preview can pull the
    latest env later. The agent's initial setup is the normal path to set this.
    """
    vercel_token = os.environ.get("VERCEL_TOKEN")
    if not vercel_token:
        return

    # Find existing env var ID
    list_url = f"{VERCEL_API_BASE}/v9/projects/{vercel_project_id}/env"
    req = urllib.request.Request(list_url, headers={"Authorization": f"Bearer {vercel_token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            envs = json.loads(resp.read().decode()).get("envs", [])
    except urllib.error.HTTPError:
        return

    existing = next(
        (e for e in envs if e.get("key") == "CMS_PREVIEW_TOKEN" and "preview" in (e.get("target") or [])),
        None,
    )

    body = json.dumps({
        "key": "CMS_PREVIEW_TOKEN",
        "value": new_token,
        "type": "encrypted",
        "target": ["preview"],
    }).encode()

    if existing:
        # Update in place
        patch_url = f"{VERCEL_API_BASE}/v9/projects/{vercel_project_id}/env/{existing['id']}"
        req = urllib.request.Request(
            patch_url,
            data=body,
            headers={
                "Authorization": f"Bearer {vercel_token}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
    else:
        # Create new
        req = urllib.request.Request(
            list_url,
            data=body,
            headers={
                "Authorization": f"Bearer {vercel_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
    try:
        urllib.request.urlopen(req).read()
    except urllib.error.HTTPError:
        pass


async def _require_admin(request: Request):
    user = await require_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.post("/admin/projects/{project_slug}/rotate-preview-token", response_model=RotateTokenResponse)
async def rotate_preview_token(project_slug: str, request: Request):
    await _require_admin(request)

    sb = get_supabase()
    p_result = (
        sb.table("projects")
        .select("id, vercel_project_id")
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    if not p_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    new_token = secrets.token_urlsafe(32)
    sb.table("projects").update({"preview_token": new_token}).eq("id", p_result.data["id"]).execute()

    if p_result.data.get("vercel_project_id"):
        _update_vercel_preview_env_var(p_result.data["vercel_project_id"], new_token)

    return {"preview_token": new_token}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "backend" && python -m pytest auth_service/tests/test_publish.py -v`
Expected: all publish tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/publish.py backend/auth_service/tests/test_publish.py
git commit -m "feat(publish): add admin rotate-preview-token endpoint that also updates Vercel env var"
```

---

## Task 9: Vercel REST API helper module

**Files:**
- Create: `backend/agent/vercel.py`
- Create: `backend/agent/tests/__init__.py`
- Create: `backend/agent/tests/test_vercel.py`

- [ ] **Step 1: Ensure agent tests directory exists**

```bash
mkdir -p "backend/agent/tests"
touch "backend/agent/tests/__init__.py"
```

Also ensure `pytest.ini` at agent level — `backend/agent/pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 2: Write failing tests**

`backend/agent/tests/test_vercel.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from .. import vercel


@pytest.fixture
def fake_urlopen():
    with patch.object(vercel, "urlopen") as mock:
        yield mock


def _json_response(data: dict, status: int = 200):
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    m.status = status
    return m


def test_find_project_by_github_repo_returns_id_if_exists(fake_urlopen):
    fake_urlopen.return_value = _json_response({
        "projects": [
            {"id": "prj_abc", "link": {"type": "github", "repo": "lauriand/portfolio"}},
        ]
    })

    result = vercel.find_project_by_repo("tok", "lauriand/portfolio")
    assert result == "prj_abc"


def test_find_project_by_github_repo_returns_none_when_missing(fake_urlopen):
    fake_urlopen.return_value = _json_response({"projects": []})

    result = vercel.find_project_by_repo("tok", "lauriand/portfolio")
    assert result is None


def test_create_project_posts_payload_and_returns_id(fake_urlopen):
    fake_urlopen.return_value = _json_response({"id": "prj_xyz", "name": "portfolio"})

    result = vercel.create_project(
        token="tok",
        name="portfolio",
        github_repo="lauriand/portfolio",
    )
    assert result == "prj_xyz"


def test_set_env_var_creates_preview_scoped(fake_urlopen):
    fake_urlopen.return_value = _json_response({"id": "env_1"})

    vercel.set_env_var(
        token="tok",
        project_id="prj_xyz",
        key="CMS_PREVIEW_TOKEN",
        value="secret",
        target=["preview"],
    )

    # Verify request body
    call = fake_urlopen.call_args[0][0]
    body = json.loads(call.data.decode())
    assert body["key"] == "CMS_PREVIEW_TOKEN"
    assert body["value"] == "secret"
    assert body["target"] == ["preview"]


def test_trigger_deployment_from_branch(fake_urlopen):
    fake_urlopen.return_value = _json_response({
        "id": "dpl_1",
        "url": "portfolio-git-cms-preview.vercel.app",
    })

    result = vercel.trigger_deployment(
        token="tok",
        project_id="prj_xyz",
        github_repo="lauriand/portfolio",
        branch="cms-preview",
    )
    assert result["url"] == "portfolio-git-cms-preview.vercel.app"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "backend" && python -m pytest agent/tests/test_vercel.py -v`
Expected: ImportError — module doesn't exist.

- [ ] **Step 4: Implement `backend/agent/vercel.py`**

```python
"""Vercel REST API helpers for the agent.

Stdlib-only HTTP (matches scan.py). All functions raise
RuntimeError on unexpected status codes so callers can log + retry.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.request import urlopen

API_BASE = "https://api.vercel.com"


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            raw = resp.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"Vercel API {method} {path} failed: {e.code} {err_body}") from e


def find_project_by_repo(token: str, github_repo: str) -> str | None:
    """Returns the Vercel project id linked to the given GitHub repo, or None."""
    data = _request(token, "GET", "/v9/projects?limit=100")
    for proj in data.get("projects", []):
        link = proj.get("link") or {}
        if link.get("type") == "github" and link.get("repo") == github_repo:
            return proj["id"]
    return None


def create_project(token: str, name: str, github_repo: str, framework: str | None = None) -> str:
    """Creates a new Vercel project linked to a GitHub repo. Returns project id."""
    owner, repo = github_repo.split("/", 1)
    payload: dict = {
        "name": name,
        "gitRepository": {
            "type": "github",
            "repo": github_repo,
        },
    }
    if framework:
        payload["framework"] = framework

    data = _request(token, "POST", "/v11/projects", payload)
    return data["id"]


def set_env_var(
    token: str,
    project_id: str,
    key: str,
    value: str,
    target: list[str],
    type_: str = "encrypted",
) -> None:
    """Upserts a Vercel env var on the given environment(s).

    `target` is a subset of: ["production", "preview", "development"].
    """
    # Find existing env var (same key + target)
    existing = _request(token, "GET", f"/v9/projects/{project_id}/env")
    for env in existing.get("envs", []):
        if env.get("key") == key and set(env.get("target") or []) == set(target):
            _request(
                token,
                "PATCH",
                f"/v9/projects/{project_id}/env/{env['id']}",
                {"value": value},
            )
            return

    _request(
        token,
        "POST",
        f"/v9/projects/{project_id}/env",
        {"key": key, "value": value, "type": type_, "target": target},
    )


def trigger_deployment(
    token: str,
    project_id: str,
    github_repo: str,
    branch: str,
) -> dict:
    """Triggers a deployment of `branch` for the Vercel project.

    Returns {"id": str, "url": str} — url is the *.vercel.app hostname.
    """
    owner, repo = github_repo.split("/", 1)
    payload = {
        "name": repo,
        "project": project_id,
        "gitSource": {
            "type": "github",
            "ref": branch,
            "repoId": None,  # Vercel looks it up from the linked project
        },
        "target": "production" if branch == "main" else None,
    }
    data = _request(token, "POST", "/v13/deployments", payload)
    return {"id": data["id"], "url": data.get("url") or ""}
```

- [ ] **Step 5: Run tests**

Run: `cd "backend" && python -m pytest agent/tests/test_vercel.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/agent/vercel.py backend/agent/tests/
git commit -m "feat(agent): add vercel.py — REST API helpers for project create/env/deploy"
```

---

## Task 10: GitHub branch creation helper

**Files:**
- Create: `backend/agent/github.py`
- Create: `backend/agent/tests/test_github.py`

- [ ] **Step 1: Write failing tests**

`backend/agent/tests/test_github.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from .. import github as gh


@pytest.fixture
def fake_urlopen():
    with patch.object(gh, "urlopen") as mock:
        yield mock


def _resp(data: dict):
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


def test_create_branch_from_main(fake_urlopen):
    # First call: get main ref → sha
    # Second call: create new ref
    fake_urlopen.side_effect = [
        _resp({"object": {"sha": "abc123"}}),
        _resp({"ref": "refs/heads/cms-preview"}),
    ]

    gh.create_branch("tok", "lauriand/portfolio", "cms-preview", from_branch="main")

    assert fake_urlopen.call_count == 2
    # Verify create payload
    create_req = fake_urlopen.call_args_list[1][0][0]
    body = json.loads(create_req.data.decode())
    assert body["ref"] == "refs/heads/cms-preview"
    assert body["sha"] == "abc123"


def test_branch_exists_returns_true_when_present(fake_urlopen):
    fake_urlopen.return_value = _resp({"object": {"sha": "xyz"}})
    assert gh.branch_exists("tok", "lauriand/portfolio", "cms-preview") is True


def test_branch_exists_returns_false_on_404(fake_urlopen):
    import urllib.error

    err = urllib.error.HTTPError(
        url="", code=404, msg="not found", hdrs=None, fp=None,
    )
    # Mimic HTTPError raised by urlopen
    fake_urlopen.side_effect = err

    assert gh.branch_exists("tok", "lauriand/portfolio", "cms-preview") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "backend" && python -m pytest agent/tests/test_github.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `backend/agent/github.py`**

```python
"""GitHub REST API helpers — stdlib only."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.request import urlopen

API_BASE = "https://api.github.com"


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urlopen(req) as resp:
        raw = resp.read().decode() or "{}"
        return json.loads(raw)


def branch_exists(token: str, github_repo: str, branch: str) -> bool:
    try:
        _request(token, "GET", f"/repos/{github_repo}/git/ref/heads/{branch}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def create_branch(token: str, github_repo: str, new_branch: str, from_branch: str = "main") -> None:
    """Creates `new_branch` from the tip of `from_branch`. No-op if branch already exists."""
    if branch_exists(token, github_repo, new_branch):
        return

    main_ref = _request(token, "GET", f"/repos/{github_repo}/git/ref/heads/{from_branch}")
    sha = main_ref["object"]["sha"]

    _request(
        token,
        "POST",
        f"/repos/{github_repo}/git/refs",
        {"ref": f"refs/heads/{new_branch}", "sha": sha},
    )
```

- [ ] **Step 4: Run tests**

Run: `cd "backend" && python -m pytest agent/tests/test_github.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/github.py backend/agent/tests/test_github.py
git commit -m "feat(agent): add github.py helper for branch exists + create"
```

---

## Task 11: Wire Vercel setup phase into `scan.py`

**Files:**
- Modify: `backend/agent/scan.py` (add flags, add `_vercel_setup` function, call after `_provision`)
- Test: `backend/agent/tests/test_scan_vercel_phase.py` (create)

- [ ] **Step 1: Write failing test**

`backend/agent/tests/test_scan_vercel_phase.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from .. import scan


def test_vercel_setup_creates_project_and_saves_urls_to_cms():
    manifest = {"project_slug": "demo"}

    with patch.object(scan, "vercel") as mock_vercel, \
         patch.object(scan, "github") as mock_gh, \
         patch.object(scan, "_http") as mock_http, \
         patch("secrets.token_urlsafe", return_value="tok32"):

        # _http GET returns None → no existing project row
        mock_http.side_effect = lambda method, url, headers, body=None: (
            None if method == "GET" else {"updated": 5}
        )

        mock_vercel.find_project_by_repo.return_value = None  # project doesn't exist yet
        mock_vercel.create_project.return_value = "prj_abc"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "dpl_1", "url": "portfolio.vercel.app"},         # prod
            {"id": "dpl_2", "url": "portfolio-git-cms-preview.vercel.app"},  # preview
        ]
        mock_gh.branch_exists.return_value = False

        scan._vercel_setup(
            manifest=manifest,
            github_repo="lauriand/portfolio",
            vercel_token="vtok",
            github_token="gtok",
            cms_api_url="http://localhost:8001",
            cms_api_token="ctok",
            cms_endpoint_base="https://cms.example.com",
        )

        mock_vercel.create_project.assert_called_once()
        mock_gh.create_branch.assert_called_once_with("gtok", "lauriand/portfolio", "cms-preview", from_branch="main")

        # Env vars set: prod + preview (2 × CMS_ENDPOINT, 1 × CMS_PREVIEW_TOKEN)
        assert mock_vercel.set_env_var.call_count == 3

        # PATCH to CMS to save vercel_project_id, production_url, preview_url, preview_token
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        patched_body = patch_calls[0][0][3]
        assert patched_body.get("vercel_project_id") == "prj_abc"
        assert patched_body.get("production_url") == "https://portfolio.vercel.app"
        assert patched_body.get("preview_url") == "https://portfolio-git-cms-preview.vercel.app"
        assert patched_body.get("preview_token") == "tok32"


def test_vercel_setup_preserves_existing_preview_token_on_rerun():
    """Idempotency: re-running against an existing project must not regenerate the token."""
    manifest = {"project_slug": "demo"}

    with patch.object(scan, "vercel") as mock_vercel, \
         patch.object(scan, "github") as mock_gh, \
         patch.object(scan, "_http") as mock_http, \
         patch("secrets.token_urlsafe", return_value="newtok_should_not_be_used"):

        # _http GET returns existing project with existing preview_token
        existing_project = {
            "github_repo": "lauriand/portfolio",
            "vercel_project_id": "prj_existing",
            "preview_token": "ORIGINAL_TOKEN",
            "production_url": "https://portfolio.vercel.app",
            "preview_url": "https://portfolio-git-cms-preview.vercel.app",
        }
        mock_http.side_effect = lambda method, url, headers, body=None: (
            existing_project if method == "GET" else {"updated": 5}
        )

        mock_vercel.find_project_by_repo.return_value = "prj_existing"
        mock_vercel.trigger_deployment.side_effect = [
            {"id": "dpl_1", "url": "portfolio.vercel.app"},
            {"id": "dpl_2", "url": "portfolio-git-cms-preview.vercel.app"},
        ]
        mock_gh.branch_exists.return_value = True

        scan._vercel_setup(
            manifest=manifest,
            github_repo="lauriand/portfolio",
            vercel_token="vtok",
            github_token="gtok",
            cms_api_url="http://localhost:8001",
            cms_api_token="ctok",
            cms_endpoint_base="https://cms.example.com",
        )

        # Idempotency: no creation of project or branch
        mock_vercel.create_project.assert_not_called()
        mock_gh.create_branch.assert_not_called()

        # PATCH was called; must have reused ORIGINAL_TOKEN, not the fresh one
        patch_calls = [c for c in mock_http.call_args_list if c[0][0] == "PATCH"]
        assert len(patch_calls) == 1
        patched_body = patch_calls[0][0][3]
        assert patched_body.get("preview_token") == "ORIGINAL_TOKEN"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "backend" && python -m pytest agent/tests/test_scan_vercel_phase.py -v`
Expected: AttributeError — `_vercel_setup` doesn't exist.

- [ ] **Step 3: Add sys.path shim to scan.py so it can be imported as `agent.scan`**

At the very top of `backend/agent/scan.py` (BEFORE any `from file_reader import ...`), add:

```python
import sys
from pathlib import Path

# Allow importing as both a script (`python scan.py`) and a package module
# (`from agent import scan`). The existing flat imports below depend on the
# agent directory being on sys.path.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
```

- [ ] **Step 4: Implement `_vercel_setup` in scan.py**

**Add imports** — in the block with `from file_reader import ...`, append:
```python
import secrets

import vercel
import github
```

**Add `_vercel_setup` function** (before `main`, around line 252):

```python
def _vercel_setup(
    manifest: dict,
    github_repo: str,
    vercel_token: str,
    github_token: str,
    cms_api_url: str,
    cms_api_token: str,
    cms_endpoint_base: str,
) -> None:
    """Creates/locates Vercel project, sets env vars, creates preview branch,
    triggers prod + preview deploys, saves URLs/token to the CMS project row.
    Idempotent: safe to re-run.
    """
    slug = manifest["project_slug"]
    click.echo(f"\n🚀 Vercel setup for {github_repo}…")

    base = cms_api_url.rstrip("/")
    headers = {"Content-Type": "application/json", "Cookie": f"access_token={cms_api_token}"}

    # 0. Fetch existing project row from CMS to check for reusable state (idempotency)
    existing = _http("GET", f"{base}/admin/projects/{slug}", headers) or {}

    # 1. Reuse preview_token if present, else generate a fresh one
    preview_token = existing.get("preview_token") or secrets.token_urlsafe(32)

    # 2. Find or create Vercel project
    project_id = vercel.find_project_by_repo(vercel_token, github_repo)
    if project_id:
        click.echo(f"  ✓ Found existing Vercel project: {project_id}")
    else:
        project_id = vercel.create_project(vercel_token, name=slug, github_repo=github_repo)
        click.echo(f"  ✓ Created Vercel project: {project_id}")

    # 3. Set env vars (upserts)
    endpoint_prod = f"{cms_endpoint_base}/content/{slug}"
    endpoint_preview = f"{cms_endpoint_base}/content/{slug}/draft"
    vercel.set_env_var(vercel_token, project_id, "CMS_ENDPOINT", endpoint_prod, target=["production"])
    vercel.set_env_var(vercel_token, project_id, "CMS_ENDPOINT", endpoint_preview, target=["preview"])
    vercel.set_env_var(vercel_token, project_id, "CMS_PREVIEW_TOKEN", preview_token, target=["preview"])
    click.echo("  ✓ Env vars set (production + preview)")

    # 4. Create cms-preview branch if missing
    if not github.branch_exists(github_token, github_repo, "cms-preview"):
        github.create_branch(github_token, github_repo, "cms-preview", from_branch="main")
        click.echo("  ✓ Created cms-preview branch")
    else:
        click.echo("  ✓ cms-preview branch already exists")

    # 5. Trigger deployments
    prod = vercel.trigger_deployment(vercel_token, project_id, github_repo, "main")
    preview = vercel.trigger_deployment(vercel_token, project_id, github_repo, "cms-preview")

    production_url = f"https://{prod['url']}" if prod.get("url") else None
    preview_url = f"https://{preview['url']}" if preview.get("url") else None
    click.echo(f"  ✓ Deployments triggered\n    prod:    {production_url}\n    preview: {preview_url}")

    # 6. Save to CMS project row via admin PATCH (base + headers already defined at top)
    _http(
        "PATCH",
        f"{base}/admin/projects/{slug}",
        headers,
        {
            "github_repo": github_repo,
            "vercel_project_id": project_id,
            "production_url": production_url,
            "preview_url": preview_url,
            "preview_token": preview_token,
        },
    )
    click.echo("  ✓ Saved Vercel metadata to CMS project row")
```

**Add CLI flags** — in `@click.command()` section (around line 254-263), add:

```python
@click.option("--github-repo", "github_repo", default=None, help="GitHub repo (OWNER/NAME) — enables Vercel setup.")
@click.option("--vercel-token", "vercel_token", default=None, envvar="VERCEL_TOKEN", help="Vercel API token (env: VERCEL_TOKEN).")
@click.option("--github-token", "github_token", default=None, envvar="GITHUB_TOKEN", help="GitHub API token (env: GITHUB_TOKEN).")
@click.option("--skip-vercel", is_flag=True, default=False, help="Skip Vercel setup even if --github-repo is given.")
```

**Update `main(...)` signature** to accept the new args:

```python
def main(
    website_dir: str | None,
    slug: str | None,
    scratch_dir: str | None,
    out_dir: str | None,
    endpoint: str,
    provision: bool,
    client_email: str | None,
    api_url: str,
    api_token: str | None,
    model: str,
    github_repo: str | None,
    vercel_token: str | None,
    github_token: str | None,
    skip_vercel: bool,
) -> None:
```

**Invoke Vercel setup** — at the end of `main`, AFTER the existing `if provision: _provision(...)` block:

```python
    # ── Optional Vercel setup ──────────────────────────────────────────────────
    if github_repo and not skip_vercel:
        if not vercel_token or not github_token:
            raise click.ClickException("--vercel-token and --github-token (or env vars) required for Vercel setup.")
        if not api_token:
            raise click.ClickException("--api-token required for Vercel setup (used to PATCH the project row).")

        # Derive CMS endpoint base from the existing --endpoint (strip any /content suffix)
        endpoint_base = endpoint.rstrip("/").rsplit("/content", 1)[0]
        _vercel_setup(
            manifest=manifest,
            github_repo=github_repo,
            vercel_token=vercel_token,
            github_token=github_token,
            cms_api_url=api_url,
            cms_api_token=api_token,
            cms_endpoint_base=endpoint_base,
        )
```

- [ ] **Step 5: Add admin GET + PATCH project endpoints in backend**

The `_vercel_setup` calls `GET /admin/projects/{slug}` and `PATCH /admin/projects/{slug}`. Neither exists yet.

Add to `backend/auth_service/models/schemas.py`:

```python
class AdminProjectPatchIn(BaseModel):
    github_repo: str | None = None
    vercel_project_id: str | None = None
    production_url: str | None = None
    preview_url: str | None = None
    preview_token: str | None = None


class AdminProjectDetailOut(BaseModel):
    slug: str
    name: str
    github_repo: str | None = None
    vercel_project_id: str | None = None
    production_url: str | None = None
    preview_url: str | None = None
    preview_token: str | None = None
    last_published_at: str | None = None
```

Add to `backend/auth_service/routers/workspace.py` (near other admin endpoints, after `admin_list_projects`):

```python
from ..models.schemas import AdminProjectPatchIn, AdminProjectDetailOut


@router.get("/admin/projects/{project_slug}", response_model=AdminProjectDetailOut)
async def admin_get_project(project_slug: str, request: Request):
    await _require_admin(request)
    sb = get_supabase()
    result = (
        sb.table("projects")
        .select("slug, name, github_repo, vercel_project_id, production_url, preview_url, preview_token, last_published_at")
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result.data


@router.patch("/admin/projects/{project_slug}")
async def admin_patch_project(project_slug: str, body: AdminProjectPatchIn, request: Request):
    await _require_admin(request)

    sb = get_supabase()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        return {"updated": 0}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    sb.table("projects").update(update_data).eq("slug", project_slug).execute()
    return {"updated": len(update_data)}
```

Add tests in `backend/auth_service/tests/test_workspace_save.py`:

```python
def test_admin_get_project_returns_vercel_fields(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data={
        "slug": "demo",
        "name": "Demo",
        "github_repo": "x/y",
        "vercel_project_id": "prj_1",
        "production_url": "https://p",
        "preview_url": "https://pr",
        "preview_token": "tok123",
        "last_published_at": None,
    })

    res = client.get("/admin/projects/demo")
    assert res.status_code == 200
    body = res.json()
    assert body["preview_token"] == "tok123"
    assert body["vercel_project_id"] == "prj_1"


def test_admin_get_project_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)
    res = client.get("/admin/projects/demo")
    assert res.status_code == 403


def test_admin_patch_project_updates_vercel_fields(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=[{"slug": "demo"}])

    res = client.patch("/admin/projects/demo", json={
        "vercel_project_id": "prj_abc",
        "production_url": "https://x.vercel.app",
        "preview_url": "https://x-preview.vercel.app",
        "preview_token": "tok",
    })
    assert res.status_code == 200

    updated = mock_supabase.update.call_args_list[0].args[0]
    assert updated["vercel_project_id"] == "prj_abc"
    assert updated["production_url"] == "https://x.vercel.app"
    assert updated["preview_url"] == "https://x-preview.vercel.app"
    assert updated["preview_token"] == "tok"


def test_admin_patch_project_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)
    res = client.patch("/admin/projects/demo", json={"preview_token": "x"})
    assert res.status_code == 403
```

- [ ] **Step 6: Run all tests**

Run: `cd "backend" && python -m pytest -v`
Expected: all tests PASS (backend + agent).

- [ ] **Step 7: Commit**

```bash
git add backend/agent/scan.py backend/agent/tests/test_scan_vercel_phase.py backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_save.py backend/auth_service/models/schemas.py
git commit -m "feat(agent): wire Vercel setup phase into scan.py with --github-repo flag + admin GET/PATCH project endpoints"
```

---

## Task 12: Frontend — `PublishConfirmModal` component

**Files:**
- Create: `frontend/src/components/dashboard/PublishConfirmModal.tsx`
- Create: `frontend/src/components/dashboard/__tests__/PublishConfirmModal.test.tsx`

- [ ] **Step 1: Verify Vitest setup exists**

Run: `cd frontend && npx vitest --version`
Expected: version number printed.

If not, check `frontend/package.json` for `vitest` — per the exploration it's present (`"test": "vitest run"`).

- [ ] **Step 2: Write failing test**

`frontend/src/components/dashboard/__tests__/PublishConfirmModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PublishConfirmModal } from "../PublishConfirmModal";

describe("PublishConfirmModal", () => {
    it("is hidden when open=false", () => {
        render(
            <PublishConfirmModal
                open={false}
                count={3}
                projectName="Laurian Portfolio"
                onCancel={() => {}}
                onConfirm={() => {}}
            />
        );
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("shows count and project name when open", () => {
        render(
            <PublishConfirmModal
                open
                count={3}
                projectName="Laurian Portfolio"
                onCancel={() => {}}
                onConfirm={() => {}}
            />
        );
        expect(screen.getByText(/3 changes/i)).toBeInTheDocument();
        expect(screen.getByText(/Laurian Portfolio/i)).toBeInTheDocument();
    });

    it("calls onCancel when Cancel is clicked", async () => {
        const user = userEvent.setup();
        const onCancel = vi.fn();
        render(
            <PublishConfirmModal open count={1} projectName="X" onCancel={onCancel} onConfirm={() => {}} />
        );
        await user.click(screen.getByRole("button", { name: /Cancel/i }));
        expect(onCancel).toHaveBeenCalledOnce();
    });

    it("calls onConfirm when Publish is clicked", async () => {
        const user = userEvent.setup();
        const onConfirm = vi.fn();
        render(
            <PublishConfirmModal open count={1} projectName="X" onCancel={() => {}} onConfirm={onConfirm} />
        );
        await user.click(screen.getByRole("button", { name: /^Publish$/i }));
        expect(onConfirm).toHaveBeenCalledOnce();
    });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npm run test -- PublishConfirmModal`
Expected: FAIL — module doesn't exist.

- [ ] **Step 4: Implement the component**

`frontend/src/components/dashboard/PublishConfirmModal.tsx`:

```tsx
"use client";

import { useEffect } from "react";

interface PublishConfirmModalProps {
    open: boolean;
    count: number;
    projectName: string;
    busy?: boolean;
    onCancel: () => void;
    onConfirm: () => void;
}

export function PublishConfirmModal({
    open,
    count,
    projectName,
    busy = false,
    onCancel,
    onConfirm,
}: PublishConfirmModalProps) {
    useEffect(() => {
        if (!open) return;
        function onEsc(e: KeyboardEvent) {
            if (e.key === "Escape" && !busy) onCancel();
        }
        window.addEventListener("keydown", onEsc);
        return () => window.removeEventListener("keydown", onEsc);
    }, [open, busy, onCancel]);

    if (!open) return null;

    return (
        <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="publish-confirm-title"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            onClick={busy ? undefined : onCancel}
        >
            <div
                className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-900"
                onClick={(e) => e.stopPropagation()}
            >
                <h2
                    id="publish-confirm-title"
                    className="text-lg font-semibold text-zinc-900 dark:text-zinc-100"
                >
                    Publish changes?
                </h2>
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    Publish {count} {count === 1 ? "change" : "changes"} to production?{" "}
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{projectName}</span>{" "}
                    will update within about 1 minute.
                </p>

                <div className="mt-6 flex justify-end gap-2">
                    <button
                        type="button"
                        disabled={busy}
                        onClick={onCancel}
                        className="cursor-pointer rounded-md border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        disabled={busy}
                        onClick={onConfirm}
                        className="cursor-pointer rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                    >
                        {busy ? "Publishing…" : "Publish"}
                    </button>
                </div>
            </div>
        </div>
    );
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm run test -- PublishConfirmModal`
Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dashboard/PublishConfirmModal.tsx frontend/src/components/dashboard/__tests__/PublishConfirmModal.test.tsx
git commit -m "feat(dashboard): add PublishConfirmModal component"
```

---

## Task 13: Frontend — `PreviewPublishBar` component

**Files:**
- Create: `frontend/src/components/dashboard/PreviewPublishBar.tsx`
- Create: `frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx`

- [ ] **Step 1: Write failing test**

`frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PreviewPublishBar } from "../PreviewPublishBar";

const mockStatus = (body: Record<string, unknown>) => ({
    ok: true,
    json: async () => body,
});

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    global.fetch = vi.fn();
});

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
});

describe("PreviewPublishBar", () => {
    it("disables See Preview when preview_url is null", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({ unpublished_count: 0, last_published_at: null, preview_url: null, production_url: null }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: /See Preview/i })).toBeDisabled();
        });
    });

    it("disables Publish Changes when unpublished_count is 0", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({
                unpublished_count: 0,
                last_published_at: "2026-04-15T10:00:00Z",
                preview_url: "https://preview.example.com",
                production_url: "https://prod.example.com",
            }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        await waitFor(() => {
            expect(screen.getByRole("button", { name: /Publish Changes/i })).toBeDisabled();
        });
    });

    it("shows 'N unpublished changes' badge when count > 0", async () => {
        (global.fetch as any).mockResolvedValueOnce(
            mockStatus({
                unpublished_count: 3,
                last_published_at: null,
                preview_url: "https://preview.example.com",
                production_url: "https://prod.example.com",
            }),
        );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        expect(await screen.findByText(/3 unpublished changes/i)).toBeInTheDocument();
    });

    it("opens modal on Publish click, confirms, calls /publish, refetches status", async () => {
        const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

        (global.fetch as any)
            // Initial status
            .mockResolvedValueOnce(
                mockStatus({
                    unpublished_count: 2,
                    last_published_at: null,
                    preview_url: "https://preview.example.com",
                    production_url: "https://prod.example.com",
                }),
            )
            // Publish POST
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ published_count: 2, last_published_at: "2026-04-16T12:00:00Z" }),
            })
            // Status refetch after publish
            .mockResolvedValueOnce(
                mockStatus({
                    unpublished_count: 0,
                    last_published_at: "2026-04-16T12:00:00Z",
                    preview_url: "https://preview.example.com",
                    production_url: "https://prod.example.com",
                }),
            );

        render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);

        const publishBtn = await screen.findByRole("button", { name: /Publish Changes/i });
        await user.click(publishBtn);

        // Modal opens
        const confirmBtn = await screen.findByRole("button", { name: /^Publish$/i });
        await user.click(confirmBtn);

        await waitFor(() => {
            const publishCall = (global.fetch as any).mock.calls.find(
                (c: any[]) => typeof c[0] === "string" && c[0].includes("/publish"),
            );
            expect(publishCall).toBeTruthy();
            expect(publishCall[1].method).toBe("POST");
        });

        // After refetch, badge disappears
        await waitFor(() => {
            expect(screen.queryByText(/unpublished changes/i)).not.toBeInTheDocument();
        });
    });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm run test -- PreviewPublishBar`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the component**

`frontend/src/components/dashboard/PreviewPublishBar.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, CheckCircle2 } from "lucide-react";
import { PublishConfirmModal } from "./PublishConfirmModal";

interface ProjectStatus {
    unpublished_count: number;
    last_published_at: string | null;
    preview_url: string | null;
    production_url: string | null;
}

interface PreviewPublishBarProps {
    projectSlug: string;
    projectName?: string;
}

const POLL_MS = 30_000;

async function fetchStatus(slug: string): Promise<ProjectStatus> {
    const r = await fetch(`/api/projects/${slug}/status`, {
        credentials: "include",
        cache: "no-store",
    });
    if (!r.ok) throw new Error(`status fetch failed: ${r.status}`);
    return r.json();
}

async function postPublish(slug: string): Promise<{ published_count: number; last_published_at: string }> {
    const r = await fetch(`/api/projects/${slug}/publish`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
    });
    if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? "Publish failed.");
    }
    return r.json();
}

function timeAgo(iso: string | null): string | null {
    if (!iso) return null;
    const delta = (Date.now() - new Date(iso).getTime()) / 1000;
    if (delta < 60) return "just now";
    if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
    return `${Math.floor(delta / 86400)}d ago`;
}

export function PreviewPublishBar({ projectSlug, projectName = "Project" }: PreviewPublishBarProps) {
    const [status, setStatus] = useState<ProjectStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [modalOpen, setModalOpen] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

    const refresh = useCallback(async () => {
        try {
            const s = await fetchStatus(projectSlug);
            setStatus(s);
        } catch {
            // Leave old status; visible via console
        } finally {
            setLoading(false);
        }
    }, [projectSlug]);

    useEffect(() => {
        refresh();
        const id = setInterval(refresh, POLL_MS);
        return () => clearInterval(id);
    }, [refresh]);

    useEffect(() => {
        if (!toast) return;
        const id = setTimeout(() => setToast(null), 4000);
        return () => clearTimeout(id);
    }, [toast]);

    async function handleConfirm() {
        setPublishing(true);
        try {
            const result = await postPublish(projectSlug);
            setModalOpen(false);
            setToast({ kind: "ok", text: `Published ${result.published_count} change${result.published_count === 1 ? "" : "s"} — live within 60 seconds.` });
            await refresh();
        } catch (err) {
            setToast({ kind: "err", text: err instanceof Error ? err.message : "Publish failed." });
        } finally {
            setPublishing(false);
        }
    }

    const count = status?.unpublished_count ?? 0;
    const hasPreview = !!status?.preview_url;
    const lastPublished = timeAgo(status?.last_published_at ?? null);

    return (
        <>
            <div className="sticky top-0 z-30 -mx-8 mb-6 flex items-center justify-between gap-4 border-b border-zinc-200 bg-white/90 px-8 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <button
                    type="button"
                    disabled={!hasPreview || loading}
                    onClick={() => status?.preview_url && window.open(status.preview_url, "_blank", "noopener,noreferrer")}
                    title={hasPreview ? "Open preview in a new tab" : "Preview not set up — contact admin"}
                    className="cursor-pointer inline-flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                >
                    <ExternalLink className="h-4 w-4" />
                    See Preview
                </button>

                <div className="flex items-center gap-3">
                    {count > 0 && (
                        <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            {count} unpublished {count === 1 ? "change" : "changes"}
                        </span>
                    )}
                    <div className="flex flex-col items-end">
                        <button
                            type="button"
                            disabled={count === 0 || publishing || loading}
                            onClick={() => setModalOpen(true)}
                            className="cursor-pointer inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                        >
                            <CheckCircle2 className="h-4 w-4" />
                            Publish Changes
                        </button>
                        {lastPublished && (
                            <span className="mt-0.5 text-[10px] text-zinc-400 dark:text-zinc-500">
                                Last published {lastPublished}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            <PublishConfirmModal
                open={modalOpen}
                count={count}
                projectName={projectName}
                busy={publishing}
                onCancel={() => setModalOpen(false)}
                onConfirm={handleConfirm}
            />

            {toast && (
                <div
                    className={
                        "fixed bottom-4 right-4 z-50 rounded-md px-4 py-2 text-sm font-medium shadow-lg " +
                        (toast.kind === "ok"
                            ? "bg-emerald-600 text-white"
                            : "bg-red-600 text-white")
                    }
                >
                    {toast.text}
                </div>
            )}
        </>
    );
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm run test -- PreviewPublishBar`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/PreviewPublishBar.tsx frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx
git commit -m "feat(dashboard): add PreviewPublishBar with status polling + publish flow"
```

---

## Task 14: Mount `PreviewPublishBar` on project overview + service editor pages

**Files:**
- Modify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`
- Modify: `frontend/src/app/dashboard/[projectSlug]/[serviceKey]/page.tsx`

- [ ] **Step 1: Add bar to project overview page**

Edit `frontend/src/app/dashboard/[projectSlug]/page.tsx`:

Add import at top:
```tsx
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
```

Inside the returned JSX, as the FIRST element inside the outer `<div className="p-8">`:
```tsx
<PreviewPublishBar projectSlug={projectSlug} projectName={project?.name ?? projectSlug} />
```

- [ ] **Step 2: Add bar to service editor page**

Edit `frontend/src/app/dashboard/[projectSlug]/[serviceKey]/page.tsx`:

Add import:
```tsx
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
```

As the FIRST element inside the outer `<div className="p-8">`:
```tsx
<PreviewPublishBar projectSlug={projectSlug} projectName={projectSlug} />
```

(Service page doesn't have the project name in context — slug is fine as fallback.)

- [ ] **Step 3: Manual smoke test — load the pages in the dev server**

Run: `cd frontend && npm run dev` (background)

In a browser, visit:
- `http://localhost:3000/dashboard/laurian-duma-portfolio`
- `http://localhost:3000/dashboard/laurian-duma-portfolio/cv`

Expected: sticky bar visible on both pages. Publish button disabled if no unpublished changes (or if endpoints aren't yet live — which is fine; we'll test functionally next). No console errors.

If `/api/projects/*/status` returns 401 because the project doesn't exist in DB, that's OK — UI should still render the bar in a disabled state.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/[projectSlug]/page.tsx frontend/src/app/dashboard/[projectSlug]/[serviceKey]/page.tsx
git commit -m "feat(dashboard): mount PreviewPublishBar on project overview + service editor"
```

---

## Task 15: Manual E2E smoke test (documented checklist + run it)

**Files:**
- Modify: `docs/superpowers/plans/2026-04-16-cms-preview-publish.md` — record smoke test result

This is a manual task — no code changes. Verify the whole system works end-to-end.

- [ ] **Step 1: Ensure env vars are set**

In the CMS backend shell:
```
export VERCEL_TOKEN=<your vercel token>
export GITHUB_TOKEN=<your github token with repo scope>
```

- [ ] **Step 2: Run agent against Laurian's portfolio**

Prerequisite: Laurian's portfolio is pushed to a GitHub repo (e.g. `stefanroman22/laurian-portfolio`). If not, push it first.

```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
python backend/agent/scan.py \
  --dir "../Laurian Duma - Portofolio Website" \
  --slug laurian-duma-portfolio \
  --provision \
  --api-token "<admin_cookie>" \
  --api-url http://localhost:8001 \
  --github-repo stefanroman22/laurian-portfolio
```

Expected output:
- "Created Vercel project: prj_..."
- "Env vars set"
- "Created cms-preview branch"
- "Deployments triggered" with prod + preview URLs
- "Saved Vercel metadata to CMS project row"

- [ ] **Step 3: Verify initial state**

1. Open CMS → login as Laurian (or admin impersonating)
2. Visit `/dashboard/laurian-duma-portfolio`
3. Confirm `PreviewPublishBar` shows:
   - See Preview button enabled (preview_url present)
   - "0 unpublished changes" badge hidden
   - Publish Changes button disabled
4. Click See Preview → opens the preview URL in new tab → Laurian's portfolio renders correctly with current content.

- [ ] **Step 4: Edit a service**

1. In CMS, click "CV" (or any key_value service)
2. Change a value (e.g., update a phone number)
3. Click Save
4. Expect: save succeeds.

- [ ] **Step 5: Verify draft/published split**

1. Open production URL (copy from the bar; or visit `preview_url` and `production_url` from `/dashboard/.../status`) in two browser tabs:
   - Production tab should still show the OLD value (published_content unchanged)
   - Preview tab (after a refresh or a deploy, which was only triggered once by the agent) should show the NEW value (draft_content)
2. `PreviewPublishBar` now shows "1 unpublished change" badge and Publish Changes enabled.

*Note:* If preview doesn't show new content, check that the preview deployment was triggered (agent output) and that the preview's env vars (`CMS_ENDPOINT`, `CMS_PREVIEW_TOKEN`) were set. Inspect in Vercel dashboard.

- [ ] **Step 6: Publish**

1. Click Publish Changes → confirm modal appears
2. Click Publish in modal → toast "Published 1 change — live within 60 seconds"
3. Wait ≤ 60 s, refresh production URL → new value now visible.

- [ ] **Step 7: Verify idempotency (re-run agent)**

```bash
python backend/agent/scan.py --dir ... --slug laurian-duma-portfolio --provision --api-token ... --github-repo stefanroman22/laurian-portfolio
```

Expected:
- "Found existing Vercel project: prj_..." (not "Created")
- "cms-preview branch already exists"
- Services already exist → provision loop skips them with a message
- Project row `preview_token` is UNCHANGED (agent fetches existing row first and reuses the token per the idempotency fix in Task 11).

Verify in Supabase: `SELECT preview_token FROM projects WHERE slug = 'laurian-duma-portfolio';` — value matches what it was before the re-run.

- [ ] **Step 8: Record smoke test result**

Append to this plan doc (or a new `docs/superpowers/plans/2026-04-16-cms-preview-publish-smoke.md`):

```markdown
## Smoke test — 2026-04-XX

- [x] Agent ran against Laurian's portfolio
- [x] See Preview opens preview URL
- [x] Editing CV shows change on preview, not prod
- [x] Publish Changes button enables, confirm modal works
- [x] After publish, prod shows new value within 60s
- [x] Agent re-run is idempotent

Issues encountered: <none / list>
```

- [ ] **Step 9: Commit**

```bash
git add docs/superpowers/plans/
git commit -m "docs: record CMS preview/publish E2E smoke test result"
```

---

## Cross-task Considerations

### Environment variables needed in backend `.env`

Add to `backend/auth_service/.env.example`:
```
VERCEL_TOKEN=
GITHUB_TOKEN=
```

(Only needed if using `rotate-preview-token` endpoint, which calls Vercel API from the backend.)

### Running both backend + frontend + agent in dev

The plan assumes:
- `cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --port 8001 --reload`
- `cd frontend && npm run dev`
- Agent is a CLI, run ad-hoc.

### Order dependencies

- **Tasks 1-8 must ship before 9-11** — the agent's PATCH calls need the endpoint, and the publish logic needs the schema.
- **Tasks 12-14 can be done in parallel with 9-11** — they only need the new backend endpoints (publish/status), which are delivered by Task 7.
- **Task 15 (smoke) is last** — requires everything.

### What to do if a task fails at runtime

- Backend tests failing after schema change: confirm migration applied via `mcp__supabase__list_tables`.
- Agent Vercel errors: check `VERCEL_TOKEN` has scope for project creation + env var management.
- GitHub 403: token needs `repo` scope (classic) or `contents:write` (fine-grained).
- Preview deployment shows stale content: re-deploy from Vercel dashboard to pick up env var changes (only needed if you manually change env vars outside the agent flow).
