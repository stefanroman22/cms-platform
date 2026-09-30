# Dashboard Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make opening, typing in, switching language in, and saving CMS content in the dashboard fast. Saving must also stop losing edits.

**Architecture:**

- Pin both Vercel projects next to the Dublin Supabase database.
- Cut redundant round-trips from the save endpoint and translate other locales in parallel.
- Make the editor use the save response instead of refetching and remounting.
- Stop TipTap from reconfiguring every editor on each keystroke.
- Prefetch on hover.
- No Redis. Justification is in the spec.

**Tech Stack:** FastAPI + supabase-py (sync) + pytest; Next.js 16 / React 19 + TipTap 3 + Vitest 4 + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-30-dashboard-speed-design.md`

## Global Constraints

**Repo and tooling**

- Repo root: `C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites`. The shell is Git Bash on Windows.
- Work on branch `perf/dashboard-speed`, which already exists and is checked out. Commit after every task. Commit messages are one line and plain, with **no `Co-Authored-By` and no AI attribution**. Never use `--no-verify`.

**Running tests**

- Backend tests: `cd backend && venv/Scripts/python -m pytest auth_service/tests/<file> -q`. The full backend suite is `make test-backend`.
- Frontend tests: `cd frontend && npx vitest run <path>`. The full frontend suite is `cd frontend && npm test`. Typecheck with `cd frontend && npx tsc --noEmit`, lint with `cd frontend && npx eslint <files>`.
- Do NOT run `npm run build` while a dev server may be running. Do NOT run `e2e/` or `backend/auth_service/tests_integration/`, because they hit production.

**Production safety**

- The Supabase DB is production. Backend tests must go through the `mock_supabase` fixture. Never call real Supabase, DeepL or Resend.

**Code rules**

- Import animation from `motion/react`, never `framer-motion`.
- Buttons keep `cursor-pointer`.
- Match the surrounding code style and comment density. Touch only what the task needs.
- ADR-0004: no in-process caches or background work that outlives a request. A `ThreadPoolExecutor` that is created and joined inside one request handler is allowed.
- ADR-0010: `services/rich_text.py` stays the only backend code that parses or serialises rich content. Do not add any.
- Response shapes (`ServiceDetailOut`, `ServiceOut`) must not change.

## Review Focus

1. **Save fails** (422/500 or a network error). The draft must stay, "Unsaved changes" must stay, no cache key may be written or invalidated, and the error banner must show. Test: Task 7.
2. **Ctrl/Cmd+S pressed repeatedly, or while a save is in flight.** Only one PUT may be sent. Test: Task 7.
3. **One locale's translation throws while the others run in parallel.** The other locales must still be upserted and the save must return 200. Test: Task 3.
4. **Hover-prefetch of a service whose GET fails (404/500).** No unhandled rejection. Opening the service afterwards must still fetch and show the error normally. Test: Task 6.
5. **Background revalidation brings a new `last_updated` while the user has unsaved edits.** The editor must NOT remount, and the draft must be kept. Test: Task 7.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `backend/vercel.json` | modify | add `"regions": ["dub1"]` |
| `frontend/vercel.json` | create | `{"regions": ["dub1"]}` |
| `docs/decisions/0004-stateless-serverless-backend.md` | modify | record the region pin |
| `backend/auth_service/routers/workspace.py` | modify | `_service_detail` helper; save uses it; parallel translation; list filter |
| `backend/auth_service/tests/test_workspace_perf.py` | create | backend tests for Tasks 2–4 |
| `frontend/src/lib/cache.ts` | modify | add `invalidatePrefix` |
| `frontend/src/lib/__tests__/cache.test.ts` | create | tests for `invalidatePrefix` |
| `frontend/src/components/dashboard/serviceApi.ts` | create | `ServiceDetail` type, `serviceDetailKey`, `fetchServiceDetail`, `prefetchServiceDetail`, `saveServiceContent`, `projectStatusKey` |
| `frontend/src/components/dashboard/__tests__/serviceApi.test.ts` | create | tests |
| `frontend/src/components/dashboard/ServiceEditor.tsx` | modify | new save flow, no remount, inert while loading, Ctrl+S, locale prefetch |
| `frontend/src/components/dashboard/__tests__/ServiceEditor.test.tsx` | modify | add save-flow tests |
| `frontend/src/components/dashboard/PreviewPublishBar.tsx` | modify | subscribe to `status:{slug}` |
| `frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx` | modify | add subscription test |
| `frontend/src/components/dashboard/rich-text/RichTextEditor.tsx` | modify | memoise options |
| `frontend/src/components/dashboard/rich-text/__tests__/RichTextEditor.test.tsx` | modify | add a no-`setOptions` test |
| `frontend/src/components/dashboard/ServiceCard.tsx` | modify | optional `onPrefetch` |
| `frontend/src/components/dashboard/ServiceGrid.tsx` | modify | optional `projectSlug`, wire prefetch |
| `frontend/src/components/dashboard/CmsSection.tsx` | modify | pass `projectSlug` to `ServiceGrid` |
| `frontend/src/components/dashboard/LocaleTabs.tsx` | modify | optional `onPrefetch` |
| `frontend/src/components/dashboard/__tests__/LocaleTabs.test.tsx`, `__tests__/ServiceGrid.test.tsx` | modify | prefetch tests |

---

### Task 1: Pin both Vercel projects to Dublin (dub1)

**Why:** Supabase is in eu-west-1 (Dublin). Both functions currently run in iad1 (Washington DC); responses carry `X-Vercel-Id: fra1::iad1::…`. Every DB call therefore crosses the Atlantic.

**Files:**
- Modify: `backend/vercel.json`
- Create: `frontend/vercel.json`
- Modify: `docs/decisions/0004-stateless-serverless-backend.md`

**Interfaces:** none.

- [ ] **Step 1: Add the region to the backend config**

In `backend/vercel.json`, add a top-level `"regions"` key directly after the `"builds"` array. The file must start like this:

```json
{
  "builds": [
    { "src": "vercel_entry.py", "use": "@vercel/python" }
  ],
  "regions": ["dub1"],
  "routes": [
```

Leave `routes` and `headers` unchanged.

- [ ] **Step 2: Create the frontend config**

Create `frontend/vercel.json`:

```json
{
  "regions": ["dub1"]
}
```

- [ ] **Step 3: Validate both files parse**

Run: `cd "/c/Users/stefa/.gemini/antigravity/scratch/CMS - websites" && python -c "import json;print(json.load(open('backend/vercel.json'))['regions'], json.load(open('frontend/vercel.json'))['regions'])"`

Expected: `['dub1'] ['dub1']`

- [ ] **Step 4: Record the decision in ADR-0004**

In `docs/decisions/0004-stateless-serverless-backend.md`, the `## Decision` list has a bullet starting `- Security headers are set at the platform layer in \`backend/vercel.json\`.` Add this bullet directly after it:

```markdown
- Both Vercel projects pin their functions to `dub1` (Dublin) via `regions` in `backend/vercel.json`
  and `frontend/vercel.json`, next to the Supabase database (eu-west-1). Every request makes several
  sequential Supabase calls, so a cross-region function (the old iad1 default) added ~80 ms per call.
```

In the same file, the `## Consequences` section ends with a `- Do NOT: …` bullet. Append this sentence to the end of that bullet's text:

` Move the functions to another region without moving the database with them.`

- [ ] **Step 5: Run the docs check**

Run: `cd "/c/Users/stefa/.gemini/antigravity/scratch/CMS - websites" && backend/venv/Scripts/python scripts/docs_check.py`

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/vercel.json frontend/vercel.json docs/decisions/0004-stateless-serverless-backend.md
git commit -m "perf(infra): pin frontend and backend functions to dub1 next to Supabase"
```

---

### Task 2: Save returns the detail without re-running auth

**Why:** `save_service` ends with `return await get_service(project_slug, service_key, request, locale=loc)`. That calls the route function, which re-runs `require_user` (1 Supabase call) and `require_project_access` (1 Supabase call) before its own select. For a bearer-token (connector) save, `require_user` is cookie-only.

**Files:**
- Modify: `backend/auth_service/routers/workspace.py`. `get_service` is at about lines 185-220; the end of `save_service` is at about line 411.
- Create: `backend/auth_service/tests/test_workspace_perf.py`

**Interfaces:**
- Produces: `_service_detail(project: dict, user, service_key: str, loc: str) -> dict`, a module-private function in `workspace.py`. It performs exactly **one** Supabase `execute()` (the `project_services` select) and returns the same dict `get_service` returned before.

- [ ] **Step 1: Write the failing test**

Create `backend/auth_service/tests/test_workspace_perf.py`:

```python
"""Performance-shape tests for the dashboard content endpoints: how many
auth/project lookups a request does, parallel translation, and list filtering."""

import threading
from unittest.mock import MagicMock

SVC_ROW = {
    "id": "svc-1",
    "service_key": "hero",
    "label": "Hero",
    "display_order": 1,
    "page_name": "General",
    "service_type_slug": "text_block",
    "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
}


def _project(locales):
    return {
        "id": "project-demo",
        "slug": "demo",
        "name": "Demo",
        "user_id": "user-client",
        "default_locale": locales[0],
        "locales": locales,
        "preview_url": None,
        "production_url": None,
        "rich_text_version": 0,
    }


def _detail_row(entries):
    return {**SVC_ROW, "content_entries": entries}


def test_save_checks_project_access_once(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)
    calls = {"n": 0}

    def fake_access(slug, user):
        calls["n"] += 1
        return _project(["en"])

    monkeypatch.setattr("auth_service.routers.workspace.require_project_access", fake_access)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_ROW),  # resolve service
        MagicMock(data=[]),  # existing rows
        MagicMock(data=[{"id": "ce-en"}]),  # upsert en
        MagicMock(  # detail re-read
            data=_detail_row(
                [
                    {
                        "locale": "en",
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T10:00:00Z",
                        "translation_meta": None,
                    }
                ]
            )
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})

    assert res.status_code == 200
    assert calls["n"] == 1
    body = res.json()
    assert body["content"] == {"title": "Hi"}
    assert body["locale"] == "en"
    assert body["last_updated"] == "2026-09-30T10:00:00Z"


def test_get_service_still_returns_detail(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl"]),
    )
    mock_supabase.execute.side_effect = [
        MagicMock(
            data=_detail_row(
                [
                    {
                        "locale": "nl",
                        "draft_content": {"title": "Hoi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T11:00:00Z",
                        "translation_meta": {},
                    },
                    {
                        "locale": "en",
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T10:00:00Z",
                        "translation_meta": None,
                    },
                ]
            )
        ),
    ]

    res = client.get("/projects/demo/services/hero?locale=nl")

    assert res.status_code == 200
    body = res.json()
    assert body["content"] == {"title": "Hoi"}
    assert body["locale"] == "nl"
    assert body["default_locale"] == "en"
    assert body["locales"] == ["en", "nl"]
    assert body["translation_status"] == {"title": "auto"}
```

- [ ] **Step 2: Run the tests and confirm the first one fails**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py -q`

Expected: `test_save_checks_project_access_once` FAILS with `assert 2 == 1`. `test_get_service_still_returns_detail` passes.

- [ ] **Step 3: Extract the helper and use it**

In `workspace.py`, replace the whole `get_service` function with these two functions:

```python
def _service_detail(project: dict, user, service_key: str, loc: str) -> dict:
    """The dashboard detail payload for one service in one locale. One Supabase
    call; the caller has already authenticated and resolved `project`."""
    default_locale = project.get("default_locale") or "en"
    sb = get_supabase_admin()
    result = (
        sb.table("project_services")
        .select(
            "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema), content_entries(locale, draft_content, published_content, updated_at, translation_meta)"
        )
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    flat = _flatten_service(result.data, loc, default_locale)
    flat["locale"] = loc
    flat["default_locale"] = default_locale
    flat["locales"] = project.get("locales") or [default_locale]
    flat["translation_status"] = _translation_status(
        result.data["service_type_slug"], result.data.get("content_entries"), loc, default_locale
    )
    flat["rich_text_version"] = int(project.get("rich_text_version") or 0)
    flat["can_edit_structure"] = bool(getattr(user, "is_admin", False))
    flat["field_formats"] = field_formats(
        result.data["service_type_slug"], flat.get("content") or {}
    )
    return flat


@router.get("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def get_service(
    project_slug: str, service_key: str, request: Request, locale: str | None = None
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)
    loc = locale or project.get("default_locale") or "en"
    return _service_detail(project, user, service_key, loc)
```

At the end of `save_service`, replace:

```python
    # Return fresh state for the edited locale
    return await get_service(project_slug, service_key, request, locale=loc)
```

with:

```python
    # Return fresh state for the edited locale. Auth and project are already
    # resolved above; re-running them would cost two more Supabase calls.
    return _service_detail(project, user, service_key, loc)
```

Search `workspace.py` for any other `await get_service(` calls, for example in `retranslate`. For each one found, apply the same replacement: `_service_detail(project, user, service_key, <locale var>)`, using the `project`/`user`/locale variables already in scope in that function. Use the same locale variable the old call passed.

- [ ] **Step 4: Run the new and existing workspace tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py auth_service/tests/test_workspace_save.py auth_service/tests/test_workspace_locale.py auth_service/tests/test_workspace_autotranslate.py auth_service/tests/test_rich_text_save.py -q`

Expected: all pass. The number and order of `execute()` calls is unchanged because `auth_as` already patched auth, so the existing ordered `side_effect` lists still line up.

If an existing test asserted on a `require_user` call count, update only that assertion, and note it in the commit.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_perf.py
git commit -m "perf(backend): save returns service detail without re-running auth and project lookup"
```

---

### Task 3: Translate other locales in parallel on a default-locale save

**Why:** On a multi-locale project, saving the default locale runs `sync_locale_draft` for each other locale **sequentially**, and each run makes 1-3 blocking DeepL HTTP calls. it-global-services has 6 locales, so that is 5 sequential rounds.

**Files:**
- Modify: `backend/auth_service/routers/workspace.py`. The block starting `if loc == default_locale:` inside `save_service` is at about lines 364-394.
- Modify: `backend/auth_service/tests/test_workspace_perf.py`

**Interfaces:**
- Consumes: `sync_locale_draft(service_type, default_content, prev_default_content, target_content, target_meta, provider, source_locale, target_locale, *, rich_text_version=0) -> tuple[dict, dict]`. It is pure apart from `provider.translate(texts: list[str], *, source: str, target: str, fmt: str) -> list[str]`.
- Consumes: `_upsert(target_locale, content, meta)`, the closure already in `save_service`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/auth_service/tests/test_workspace_perf.py`:

```python
class _BarrierProvider:
    """Every translate() waits on a barrier sized to the number of target
    locales. Run sequentially, the first call times out (BrokenBarrierError),
    so this only succeeds when the locales are translated concurrently."""

    def __init__(self, parties, fail_target=None):
        self.barrier = threading.Barrier(parties, timeout=3)
        self.fail_target = fail_target

    def translate(self, texts, *, source, target, fmt):
        self.barrier.wait()
        if target == self.fail_target:
            raise RuntimeError("deepl down for " + target)
        return [f"[{target}] {t}" for t in texts]


def _content_upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


def _multi_locale_side_effect(n_upserts):
    return (
        [MagicMock(data=SVC_ROW), MagicMock(data=[])]
        + [MagicMock(data=[{"id": f"ce-{i}"}]) for i in range(n_upserts)]
        + [
            MagicMock(
                data=_detail_row(
                    [
                        {
                            "locale": "en",
                            "draft_content": {"title": "Hi"},
                            "published_content": None,
                            "updated_at": "2026-09-30T10:00:00Z",
                            "translation_meta": None,
                        }
                    ]
                )
            )
        ]
    )


def test_default_save_translates_locales_concurrently(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl", "de", "fr"]),
    )
    monkeypatch.setattr(
        "auth_service.routers.workspace.pg_rate_limit.enforce", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "auth_service.routers.workspace.get_provider", lambda: _BarrierProvider(3)
    )
    mock_supabase.execute.side_effect = _multi_locale_side_effect(4)

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})

    assert res.status_code == 200
    ups = _content_upserts(mock_supabase)
    # Default first, then the others in project-locale order (deterministic writes).
    assert [u["locale"] for u in ups] == ["en", "nl", "de", "fr"]
    assert ups[1]["draft_content"] == {"title": "[nl] Hi"}
    assert ups[3]["draft_content"] == {"title": "[fr] Hi"}


def test_one_locale_failing_does_not_block_the_others(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl", "de", "fr"]),
    )
    monkeypatch.setattr(
        "auth_service.routers.workspace.pg_rate_limit.enforce", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "auth_service.routers.workspace.get_provider",
        lambda: _BarrierProvider(3, fail_target="de"),
    )
    mock_supabase.execute.side_effect = _multi_locale_side_effect(3)

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})

    assert res.status_code == 200
    assert [u["locale"] for u in _content_upserts(mock_supabase)] == ["en", "nl", "fr"]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py -q -k "concurrently or failing"`

Expected: both FAIL. With sequential translation, the barrier breaks after 3 s, so every locale's translate raises, is logged and skipped, and the upsert locale list is `["en"]`.

If `get_provider` or `pg_rate_limit` are not module attributes of `workspace` under those names, open `workspace.py`'s imports and use the exact names shown there. They are currently `from ..core import pg_rate_limit` and `from ..translation import get_provider`.

- [ ] **Step 3: Implement parallel translation**

In `workspace.py`, add to the imports at the top:

```python
import copy
from concurrent.futures import ThreadPoolExecutor
```

Keep imports sorted the way ruff/isort expects: stdlib imports alphabetised, `copy` before `logging`, and the `from concurrent.futures import ThreadPoolExecutor` line among the `from` stdlib imports. Run `make format` if unsure.

Add this constant near `STORAGE_BUCKET`:

```python
# Upper bound on concurrent machine-translation calls in one save request.
MAX_TRANSLATE_WORKERS = 8
```

Replace this block inside `save_service`:

```python
        other_locales = [t for t in locales if t != default_locale]
        if other_locales:
            provider = get_provider()
            for target in other_locales:
                trow = by_locale.get(target) or {}
                try:
                    new_content, new_meta = sync_locale_draft(
                        service_type,
                        content_in,
                        prev_default,
                        trow.get("draft_content"),
                        trow.get("translation_meta") or {},
                        provider,
                        default_locale,
                        target,
                        rich_text_version=version,
                    )
                    _upsert(target, new_content, new_meta)
                except Exception:  # noqa: BLE001 — resilience: never fail the save
                    logger.exception(
                        "auto-translate failed for %s/%s locale %s (row unchanged)",
                        project_slug,
                        service_key,
                        target,
                    )
```

with:

```python
        other_locales = [t for t in locales if t != default_locale]
        if other_locales:
            provider = get_provider()

            # Each worker gets its own deep copies so no two threads share a
            # mutable dict. The pool lives and is joined inside this request.
            def _translate(target: str) -> tuple[dict, dict]:
                trow = by_locale.get(target) or {}
                return sync_locale_draft(
                    service_type,
                    copy.deepcopy(content_in),
                    copy.deepcopy(prev_default),
                    copy.deepcopy(trow.get("draft_content")),
                    copy.deepcopy(trow.get("translation_meta") or {}),
                    provider,
                    default_locale,
                    target,
                    rich_text_version=version,
                )

            workers = min(len(other_locales), MAX_TRANSLATE_WORKERS)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {t: pool.submit(_translate, t) for t in other_locales}
                # Upserts stay in this thread, in locale order: deterministic writes
                # and no shared Supabase client across threads.
                for target in other_locales:
                    try:
                        new_content, new_meta = futures[target].result()
                        _upsert(target, new_content, new_meta)
                    except Exception:  # noqa: BLE001 — resilience: never fail the save
                        logger.exception(
                            "auto-translate failed for %s/%s locale %s (row unchanged)",
                            project_slug,
                            service_key,
                            target,
                        )
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py auth_service/tests/test_workspace_autotranslate.py auth_service/tests/test_workspace_locale.py auth_service/tests/test_translation_sync.py auth_service/tests/test_rich_text_save.py -q`

Expected: all pass.

- [ ] **Step 5: Lint**

Run: `cd "/c/Users/stefa/.gemini/antigravity/scratch/CMS - websites" && backend/venv/Scripts/python -m ruff check backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_perf.py && backend/venv/Scripts/python -m black --check backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_perf.py`

Expected: clean. If it is not clean, run `make format`, re-run, and include the formatting in the commit.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_perf.py
git commit -m "perf(backend): translate other locales in parallel on default-locale save"
```

---

### Task 4: List services fetches only the locales it shows

**Why:** `GET /projects/{slug}/services` embeds every locale's full draft and published JSON for every service, but `_flatten_service` uses only the requested locale, falling back to the default locale.

**Files:**
- Modify: `backend/auth_service/routers/workspace.py`, the `list_services` function at about lines 159-182.
- Modify: `backend/auth_service/tests/test_workspace_perf.py`

**Interfaces:** none new.

- [ ] **Step 1: Write the failing test**

Append to `test_workspace_perf.py`:

```python
def test_list_services_embeds_only_needed_locales(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl", "de"]),
    )
    mock_supabase.execute.side_effect = [
        MagicMock(
            data=[
                {
                    **SVC_ROW,
                    "content_entries": [
                        {
                            "locale": "en",
                            "updated_at": "2026-09-30T10:00:00Z",
                            "draft_content": {"title": "Hi"},
                            "published_content": None,
                        }
                    ],
                }
            ]
        )
    ]

    res = client.get("/projects/demo/services?locale=nl")

    assert res.status_code == 200
    # nl requested, falls back to the default (en) row.
    assert res.json()[0]["content"] == {"title": "Hi"}
    embed_filters = [
        c.args for c in mock_supabase.in_.call_args_list if c.args[0] == "content_entries.locale"
    ]
    assert len(embed_filters) == 1
    assert sorted(embed_filters[0][1]) == ["en", "nl"]


def test_list_services_default_locale_filters_to_one(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl"]),
    )
    mock_supabase.execute.side_effect = [MagicMock(data=[])]

    res = client.get("/projects/demo/services")

    assert res.status_code == 200
    embed_filters = [
        c.args for c in mock_supabase.in_.call_args_list if c.args[0] == "content_entries.locale"
    ]
    assert embed_filters == [("content_entries.locale", ["en"])]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py -q -k list_services`

Expected: both FAIL, because `in_` is never called with `content_entries.locale`.

- [ ] **Step 3: Implement the filter**

In `list_services`, change the query chain from:

```python
            .eq("project_id", project["id"])
            .order("display_order")
            .execute()
```

to:

```python
            .eq("project_id", project["id"])
            # Filter the embedded rows (not the services) to the locale shown plus
            # its default-locale fallback; other locales' JSON is never used here.
            .in_("content_entries.locale", sorted({loc, default_locale}))
            .order("display_order")
            .execute()
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_workspace_perf.py -q && make -C "/c/Users/stefa/.gemini/antigravity/scratch/CMS - websites" test-backend`

Expected: all pass. If `make` is unavailable, run `cd backend && venv/Scripts/python -m pytest auth_service/tests/ -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_perf.py
git commit -m "perf(backend): list services embeds only the shown and default locale rows"
```

---

### Task 5: `cache.invalidatePrefix`

**Files:**
- Modify: `frontend/src/lib/cache.ts`. Add it after `invalidate`.
- Create: `frontend/src/lib/__tests__/cache.test.ts`

**Interfaces:**
- Produces: `export function invalidatePrefix(prefix: string, opts?: { except?: string }): void`. It removes every in-memory entry whose key starts with `prefix`, except `opts.except`, deletes any persisted copy, and notifies each removed key's subscribers.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/__tests__/cache.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import * as cache from "@/lib/cache";

beforeEach(() => cache.clearAll());

describe("invalidatePrefix", () => {
  it("removes matching keys, keeps the excepted key and others, and notifies", () => {
    cache.set("service:demo:about:default", 1);
    cache.set("service:demo:about:en", 2);
    cache.set("service:demo:hero:en", 3);
    cache.set("services:demo", 4);
    const onEn = vi.fn();
    const onDefault = vi.fn();
    cache.subscribe("service:demo:about:en", onEn);
    cache.subscribe("service:demo:about:default", onDefault);

    cache.invalidatePrefix("service:demo:about:", { except: "service:demo:about:default" });

    expect(cache.get("service:demo:about:en")).toBeNull();
    expect(cache.get("service:demo:about:default")).toBe(1);
    expect(cache.get("service:demo:hero:en")).toBe(3);
    expect(cache.get("services:demo")).toBe(4);
    expect(onEn).toHaveBeenCalledTimes(1);
    expect(onDefault).not.toHaveBeenCalled();
  });

  it("is a no-op when nothing matches", () => {
    cache.set("services:demo", 4);
    expect(() => cache.invalidatePrefix("service:nope:")).not.toThrow();
    expect(cache.get("services:demo")).toBe(4);
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/cache.test.ts`

Expected: FAIL, `cache.invalidatePrefix is not a function`.

- [ ] **Step 3: Implement**

In `frontend/src/lib/cache.ts`, directly after the `invalidate` function, add:

```ts
/**
 * Invalidate every key starting with `prefix` (e.g. all locales of one
 * service after a save re-translated them), except `opts.except`.
 */
export function invalidatePrefix(prefix: string, opts: { except?: string } = {}): void {
  for (const key of Array.from(store.keys())) {
    if (key.startsWith(prefix) && key !== opts.except) invalidate(key);
  }
}
```

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/lib/__tests__/cache.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/cache.ts frontend/src/lib/__tests__/cache.test.ts
git commit -m "feat(frontend): cache.invalidatePrefix"
```

---

### Task 6: Shared service API module with prefetch

**Why:** The editor, service cards and locale tabs must share one fetcher and one cache-key format, or prefetched entries will not be found.

**Files:**
- Create: `frontend/src/components/dashboard/serviceApi.ts`
- Create: `frontend/src/components/dashboard/__tests__/serviceApi.test.ts`
- Modify: `frontend/src/components/dashboard/ServiceEditor.tsx`. Remove the moved code and import it instead.

**Interfaces:**
- Consumes: `cache.prefetch(key, fetcher)` from `@/lib/cache`, which already exists and dedupes in-flight requests and skips entries fresher than 5 minutes.
- Produces (all exported from `@/components/dashboard/serviceApi`):
  - `interface ServiceDetail`, identical to the one currently in `ServiceEditor.tsx`
  - `serviceDetailKey(projectSlug: string, serviceKey: string, locale?: string): string` → `` `service:${projectSlug}:${serviceKey}:${locale || "default"}` ``
  - `serviceDetailPrefix(projectSlug: string, serviceKey: string): string` → `` `service:${projectSlug}:${serviceKey}:` ``
  - `servicesListKey(projectSlug: string): string` → `` `services:${projectSlug}` ``. This must equal the key `CmsSection` uses. Check `CmsSection.tsx` (`servicesKey`) and make it match exactly.
  - `projectStatusKey(projectSlug: string): string` → `` `status:${projectSlug}` ``
  - `fetchServiceDetail(projectSlug: string, serviceKey: string, locale?: string): Promise<ServiceDetail>`
  - `saveServiceContent(projectSlug: string, serviceKey: string, content: Record<string, unknown>, locale?: string): Promise<ServiceDetail>`. This is the old `saveContent` with the same error mapping, but it returns `r.json()` on success.
  - `prefetchServiceDetail(projectSlug: string, serviceKey: string, locale?: string): void`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/dashboard/__tests__/serviceApi.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as cache from "@/lib/cache";
import {
  serviceDetailKey,
  serviceDetailPrefix,
  projectStatusKey,
  prefetchServiceDetail,
  saveServiceContent,
} from "../serviceApi";

beforeEach(() => cache.clearAll());
afterEach(() => vi.restoreAllMocks());

describe("keys", () => {
  it("formats detail keys with a default-locale fallback", () => {
    expect(serviceDetailKey("demo", "about")).toBe("service:demo:about:default");
    expect(serviceDetailKey("demo", "about", "en")).toBe("service:demo:about:en");
    expect(serviceDetailPrefix("demo", "about")).toBe("service:demo:about:");
    expect(projectStatusKey("demo")).toBe("status:demo");
  });
});

describe("prefetchServiceDetail", () => {
  it("fetches once and caches under the detail key", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "s1" }) });
    prefetchServiceDetail("demo", "about", "en");
    prefetchServiceDetail("demo", "about", "en");
    await vi.waitFor(() => expect(cache.get(serviceDetailKey("demo", "about", "en"))).toEqual({ id: "s1" }));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/projects/demo/services/about?locale=en"
    );
  });

  it("swallows a failed prefetch without caching or an unhandled rejection", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
    prefetchServiceDetail("demo", "missing");
    await new Promise((r) => setTimeout(r, 20));
    process.off("unhandledRejection", unhandled);
    expect(cache.get(serviceDetailKey("demo", "missing"))).toBeNull();
    expect(cache.getInflight(serviceDetailKey("demo", "missing"))).toBeNull();
    expect(unhandled).not.toHaveBeenCalled();
  });
});

describe("saveServiceContent", () => {
  it("returns the saved detail", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "s1", content: { a: 1 } }) });
    await expect(saveServiceContent("demo", "about", { a: 1 })).resolves.toEqual({ id: "s1", content: { a: 1 } });
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/projects/demo/services/about");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ content: { a: 1 } });
  });

  it("maps a string detail to the error message", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "Too long" }) });
    await expect(saveServiceContent("demo", "about", {})).rejects.toThrow("Too long");
  });
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/serviceApi.test.ts`

Expected: FAIL, because the module does not exist.

- [ ] **Step 3: Create the module**

Create `frontend/src/components/dashboard/serviceApi.ts`:

```ts
import * as cache from "@/lib/cache";
import type { FieldFormat } from "@/components/dashboard/rich-text/ContentField";

/** Dashboard detail payload for one service in one locale (`ServiceDetailOut`). */
export interface ServiceDetail {
  id: string;
  service_key: string;
  label: string | null;
  service_type_slug: string;
  service_type_name: string;
  service_type_icon: string;
  schema: Record<string, unknown>;
  content: Record<string, unknown>;
  last_updated: string | null;
  locale?: string;
  default_locale?: string;
  locales?: string[];
  translation_status?: Record<string, string> | null;
  rich_text_version?: number;
  field_formats?: Record<string, FieldFormat>;
  can_edit_structure?: boolean;
}

// Cache keys shared by the editor, the service cards and the locale tabs, so a
// hover prefetch lands exactly where the editor will look for it.
export const serviceDetailKey = (projectSlug: string, serviceKey: string, locale?: string) =>
  `service:${projectSlug}:${serviceKey}:${locale || "default"}`;
export const serviceDetailPrefix = (projectSlug: string, serviceKey: string) =>
  `service:${projectSlug}:${serviceKey}:`;
export const servicesListKey = (projectSlug: string) => `services:${projectSlug}`;
export const projectStatusKey = (projectSlug: string) => `status:${projectSlug}`;

export function fetchServiceDetail(
  projectSlug: string,
  serviceKey: string,
  locale?: string
): Promise<ServiceDetail> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  return fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    credentials: "include",
    cache: "no-store",
  }).then((r) => {
    if (!r.ok) throw new Error("Failed to load service.");
    return r.json();
  });
}

export async function saveServiceContent(
  projectSlug: string,
  serviceKey: string,
  content: Record<string, unknown>,
  locale?: string
): Promise<ServiceDetail> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  const r = await fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    const d = b.detail;
    throw new Error(
      Array.isArray(d)
        ? d.map((x) => x?.msg ?? String(x)).join("; ")
        : typeof d === "string"
          ? d
          : "Save failed"
    );
  }
  return r.json();
}

/** Warm the cache on hover/focus so opening the service is instant. */
export function prefetchServiceDetail(projectSlug: string, serviceKey: string, locale?: string) {
  cache.prefetch(serviceDetailKey(projectSlug, serviceKey, locale), () =>
    fetchServiceDetail(projectSlug, serviceKey, locale)
  );
}
```

If the unhandled-rejection test fails, the cause is `cache.setInflight`. It attaches `.then(...).catch(...)`, so the original promise is handled, but check it. The fix goes in `prefetchServiceDetail`: pass `() => fetchServiceDetail(...)` unchanged. Do NOT change `cache.ts` semantics. If a rejection still escapes, wrap the fetcher as `() => { const p = fetchServiceDetail(...); p.catch(() => {}); return p; }` and add a one-line comment explaining why.

- [ ] **Step 4: Point ServiceEditor at the module (no behaviour change yet)**

In `ServiceEditor.tsx`:

- Delete the local `interface ServiceDetail`, `fetchServiceDetail` and `saveContent`.
- Delete the `import type { FieldFormat } ...` line if nothing else in the file uses it.
- Add:

```ts
import {
  type ServiceDetail,
  fetchServiceDetail,
  saveServiceContent,
  serviceDetailKey,
} from "@/components/dashboard/serviceApi";
```

Replace:

```ts
  const cacheKey = `service:${projectSlug}:${serviceKey}:${localeParam || "default"}`;
```

with:

```ts
  const cacheKey = serviceDetailKey(projectSlug, serviceKey, localeParam || undefined);
```

In `handleSave`, replace the call to `saveContent(` with `saveServiceContent(`. The same arguments work; the return value is ignored for now.

- [ ] **Step 5: Run the tests, typecheck and lint**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/serviceApi.test.ts src/components/dashboard/__tests__/ServiceEditor.test.tsx && npx tsc --noEmit && npx eslint src/components/dashboard/serviceApi.ts src/components/dashboard/ServiceEditor.tsx`

Expected: all pass and clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dashboard/serviceApi.ts frontend/src/components/dashboard/__tests__/serviceApi.test.ts frontend/src/components/dashboard/ServiceEditor.tsx
git commit -m "refactor(frontend): shared service API module with prefetch and shared cache keys"
```

---

### Task 7: Save flow — use the response, no remount, keep in-flight edits, Ctrl+S, fresh publish bar

**Why:** Four problems in the current save flow:

- After a save, `handleSave` calls `refresh()`, which is a second GET.
- The new `last_updated` changes `<EditorComponent key={service.last_updated}>`, which remounts every editor: focus, cursor and undo are lost.
- `setDraft(null)` wipes anything typed during the save.
- Other locales, the grid list and the publish bar stay stale.

**Files:**
- Modify: `frontend/src/components/dashboard/ServiceEditor.tsx`
- Modify: `frontend/src/components/dashboard/PreviewPublishBar.tsx`
- Modify: `frontend/src/components/dashboard/__tests__/ServiceEditor.test.tsx`
- Modify: `frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx`

**Interfaces:**
- Consumes (Task 5): `cache.invalidatePrefix(prefix, { except })`.
- Consumes (Task 6): `serviceDetailPrefix`, `servicesListKey`, `projectStatusKey`, and `saveServiceContent`, which returns `Promise<ServiceDetail>`.
- Contract: `PreviewPublishBar` refreshes whenever `cache.invalidate(projectStatusKey(slug))` fires.

**Context for the tests:**

- `ServiceEditor.test.tsx` uses a `text_block` with `rich_text_version: 0`. The editor is therefore a plain `<textarea placeholder="Write content here…">`, initial value `"World"`, found with `findByPlaceholderText(/write content here/i)`.
- `mockFetch(put)` in that file returns `DETAIL` for GETs.

- [ ] **Step 1: Write the failing ServiceEditor tests**

In `ServiceEditor.test.tsx`, add `act` to the `@testing-library/react` import. Then append the following at the end of the file:

```tsx
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function getCalls() {
  return (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
}
const gets = () => getCalls().filter(([, init]) => !init || !init.method || init.method === "GET");
const puts = () => getCalls().filter(([, init]) => init?.method === "PUT");

const SAVED = { ...DETAIL, content: { title: "Hello", body: "World more" }, last_updated: "2026-09-30T12:00:00Z" };

describe("ServiceEditor save flow", () => {
  it("uses the PUT response: no refetch, no remount, clean afterwards", async () => {
    mockFetch({ status: 200, body: SAVED });
    const user = await renderAndType();
    const before = screen.getByPlaceholderText(/write content here/i);
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByText(/changes saved successfully/i)).toBeInTheDocument();
    expect(gets()).toHaveLength(1); // only the initial load
    const after = screen.getByPlaceholderText(/write content here/i);
    expect(after).toBe(before); // same DOM node → editor was not remounted
    expect(after).toHaveValue("World more");
    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument();
    expect(cache.get("service:demo:about:default")).toEqual(SAVED);
  });

  it("keeps text typed while the save is in flight, and stays dirty", async () => {
    const put = deferred<unknown>();
    global.fetch = vi.fn().mockImplementation(async (_u: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        await put.promise;
        return { ok: true, status: 200, json: async () => SAVED };
      }
      return { ok: true, status: 200, json: async () => DETAIL };
    });
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await user.type(screen.getByPlaceholderText(/write content here/i), " again");
    await act(async () => put.resolve(undefined));
    await screen.findByText(/changes saved successfully/i);
    expect(screen.getByPlaceholderText(/write content here/i)).toHaveValue("World more again");
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });

  it("invalidates other locales, the grid list and the publish status", async () => {
    mockFetch({ status: 200, body: SAVED });
    cache.set("service:demo:about:en", { stale: true });
    cache.set("service:demo:hero:en", { other: true });
    const onStatus = vi.fn();
    const onList = vi.fn();
    cache.subscribe("status:demo", onStatus);
    cache.subscribe("services:demo", onList);
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    await screen.findByText(/changes saved successfully/i);
    expect(cache.get("service:demo:about:en")).toBeNull();
    expect(cache.get("service:demo:hero:en")).toEqual({ other: true });
    expect(onStatus).toHaveBeenCalled();
    expect(onList).toHaveBeenCalled();
  });

  it("on a failed save keeps the draft and touches no cache", async () => {
    mockFetch({ status: 500, body: { detail: "boom" } });
    cache.set("service:demo:about:en", { keep: true });
    const onStatus = vi.fn();
    cache.subscribe("status:demo", onStatus);
    const user = await renderAndType();
    await user.click(screen.getByRole("button", { name: /^save$/i }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/write content here/i)).toHaveValue("World more");
    expect(cache.get("service:demo:about:en")).toEqual({ keep: true });
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("Ctrl+S saves once, even when pressed repeatedly during a save", async () => {
    const put = deferred<unknown>();
    global.fetch = vi.fn().mockImplementation(async (_u: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        await put.promise;
        return { ok: true, status: 200, json: async () => SAVED };
      }
      return { ok: true, status: 200, json: async () => DETAIL };
    });
    const user = await renderAndType();
    await user.keyboard("{Control>}s{/Control}");
    await user.keyboard("{Control>}s{/Control}");
    await user.keyboard("{Meta>}s{/Meta}");
    await act(async () => put.resolve(undefined));
    await screen.findByText(/changes saved successfully/i);
    expect(puts()).toHaveLength(1);
  });

  it("does not remount or drop the draft when a background refresh brings a newer version", async () => {
    await renderAndType();
    const before = screen.getByPlaceholderText(/write content here/i);
    act(() => {
      cache.set("service:demo:about:default", { ...DETAIL, last_updated: "2026-09-30T13:00:00Z" });
    });
    const after = screen.getByPlaceholderText(/write content here/i);
    expect(after).toBe(before);
    expect(after).toHaveValue("World more");
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });

  it("remounts with the new content when a newer version arrives while clean", async () => {
    render(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    await screen.findByPlaceholderText(/write content here/i);
    act(() => {
      cache.set("service:demo:about:default", {
        ...DETAIL,
        content: { title: "Hello", body: "Changed elsewhere" },
        last_updated: "2026-09-30T13:00:00Z",
      });
    });
    expect(await screen.findByDisplayValue("Changed elsewhere")).toBeInTheDocument();
  });

  it("makes the editor inert and disables Save while another locale loads", async () => {
    const { rerender } = render(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    await screen.findByPlaceholderText(/write content here/i);
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {})); // en never resolves
    mockSearch = "locale=en";
    rerender(<ServiceEditor projectSlug="demo" serviceKey="about" onBack={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("service-editor-body")).toHaveAttribute("inert"));
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/ServiceEditor.test.tsx`

Expected: the new tests fail, for reasons such as an extra GET, a node not being the same element, a missing testid, or more than one PUT. The old tests pass.

- [ ] **Step 3: Implement the ServiceEditor changes**

In `ServiceEditor.tsx`:

(a) Change the imports:

- `import { useState, useEffect, useCallback, useRef } from "react";`
- `import * as cache from "@/lib/cache";`
- Extend the serviceApi import with `serviceDetailPrefix, servicesListKey, projectStatusKey`. Do NOT import `prefetchServiceDetail` yet; Task 9 adds it.

(b) After the `useState` declarations, add:

```ts
  // Bumped only when content changes underneath us (re-translate, or a newer
  // server version arriving while there are no unsaved edits). Our own save
  // never remounts the editor, so focus, cursor and undo history survive it.
  const [editorRevision, setEditorRevision] = useState(0);
  const ownSaveStampRef = useRef<string | null>(null);
  const seenStampRef = useRef<string | null | undefined>(undefined);
  // Counts edits so a save only clears the draft if nothing was typed meanwhile.
  const changeSeqRef = useRef(0);
  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);
  const savingRef = useRef(false);
```

(c) Directly after that, add the remount decision effect:

```ts
  useEffect(() => {
    if (!service) return;
    const stamp = service.last_updated;
    if (seenStampRef.current === undefined) {
      seenStampRef.current = stamp;
      return;
    }
    if (stamp === seenStampRef.current) return;
    seenStampRef.current = stamp;
    if (stamp !== null && stamp === ownSaveStampRef.current) return; // our own save
    if (draftRef.current !== null) return; // never clobber unsaved edits
    setEditorRevision((r) => r + 1);
  }, [service]);
```

(d) Replace `handleChange` with:

```ts
  const handleChange = useCallback((content: Record<string, unknown>) => {
    changeSeqRef.current += 1;
    setDraft(content);
    setSaveSuccess(false);
  }, []);
```

(e) Replace the whole `async function handleSave() { ... }` with:

```ts
  async function handleSave() {
    if (!service || savingRef.current || loading) return;
    const content = draft ?? service.content;
    const seqAtStart = changeSeqRef.current;
    savingRef.current = true;
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);
    try {
      const saved = await saveServiceContent(
        projectSlug,
        serviceKey,
        content,
        localeParam || undefined
      );
      ownSaveStampRef.current = saved.last_updated;
      // Other locales were re-translated server-side; the grid's dates and the
      // publish bar's unpublished count changed too.
      cache.invalidatePrefix(serviceDetailPrefix(projectSlug, serviceKey), { except: cacheKey });
      cache.set(cacheKey, saved);
      cache.invalidate(servicesListKey(projectSlug));
      cache.invalidate(projectStatusKey(projectSlug));
      setSaveSuccess(true);
      if (changeSeqRef.current === seqAtStart) setDraft(null);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  const handleSaveRef = useRef(handleSave);
  useEffect(() => {
    handleSaveRef.current = handleSave;
  });

  // Ctrl/Cmd+S saves (and never opens the browser's "Save page" dialog).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void handleSaveRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
```

(f) In `handleRetranslate`, after `setDraft(null);` and before `refresh();`, add:

```ts
      cache.invalidate(projectStatusKey(projectSlug));
```

(g) Change the Save button's `disabled={saving}` to `disabled={saving || loading}`.

(h) In the editor block, replace:

```tsx
        <div className="relative">
```

with:

```tsx
        <div className="relative" data-testid="service-editor-body" inert={loading} aria-busy={loading}>
```

Then replace `key={service.last_updated ?? ""}` on `<EditorComponent` with `key={editorRevision}`. Update the comment above the block to say that the editor is inert while another locale loads, so typing can't land in the wrong language.

If TypeScript rejects `inert={loading}` (React 19 types accept `inert?: boolean`), check the `@types/react` version in `frontend/package.json`. React 19 types support it; do not use a string.

- [ ] **Step 4: Make PreviewPublishBar refresh on `status:{slug}`**

In `PreviewPublishBar.tsx`, add the imports:

```ts
import * as cache from "@/lib/cache";
import { projectStatusKey } from "./serviceApi";
```

After the existing polling `useEffect`, add:

```ts
  // Saves and re-translates elsewhere in the dashboard invalidate this key so
  // the unpublished count (and the Publish button) update at once, not on the
  // next 30s poll.
  useEffect(() => cache.subscribe(projectStatusKey(projectSlug), refresh), [projectSlug, refresh]);
```

`cache.subscribe` returns its unsubscribe function, so it doubles as the effect cleanup. The listener signature is `() => void`, and `refresh` returns a promise. If the TypeScript or lint rule `no-misused-promises` complains, wrap it as `() => void refresh()`.

- [ ] **Step 5: Add the PreviewPublishBar test**

Append inside the `describe("PreviewPublishBar", ...)` block in `PreviewPublishBar.test.tsx`:

```tsx
  it("refetches status immediately when status:{slug} is invalidated", async () => {
    const { invalidate } = await import("@/lib/cache");
    (global.fetch as MockFetch).mockResolvedValue(
      mockStatus({
        unpublished_count: 0,
        last_published_at: null,
        preview_url: null,
        production_url: null,
      })
    );
    render(<PreviewPublishBar projectSlug="demo" projectName="Demo" />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    invalidate("status:demo");
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  });
```

- [ ] **Step 6: Run the tests, typecheck and lint**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/ServiceEditor.test.tsx src/components/dashboard/__tests__/PreviewPublishBar.test.tsx src/components/dashboard/__tests__/CmsSection.test.tsx && npx tsc --noEmit && npx eslint src/components/dashboard/ServiceEditor.tsx src/components/dashboard/PreviewPublishBar.tsx`

Expected: all pass and clean.

If the "remounts with the new content when … clean" test fails: `TextBlockEditor` must seed from `initialContent` on mount. Confirm that remounting via `key={editorRevision}` happens; it should, because the effect bumps the revision.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/dashboard/ServiceEditor.tsx frontend/src/components/dashboard/PreviewPublishBar.tsx frontend/src/components/dashboard/__tests__/ServiceEditor.test.tsx frontend/src/components/dashboard/__tests__/PreviewPublishBar.test.tsx
git commit -m "perf(dashboard): save uses the response, keeps the editor mounted and in-flight edits, Ctrl+S, instant publish status"
```

---

### Task 8: Rich-text editor stops reconfiguring on every render

**Why:** `useEditor` without deps compares `extensions` (element identity), `editorProps` (identity) and `content` (value) against the live editor on every render. All three change every render: `inlineExtensions(placeholder)` builds new instances, `editorProps` is a new literal, and `value` changes on each keystroke. So `editor.setOptions()` runs on every render of every `RichTextEditor`, and a keystroke in one field re-renders all its siblings. The comparison is in `node_modules/@tiptap/react/src/useEditor.ts`, `compareOptions`.

**Files:**
- Modify: `frontend/src/components/dashboard/rich-text/RichTextEditor.tsx`
- Modify: `frontend/src/components/dashboard/rich-text/__tests__/RichTextEditor.test.tsx`

**Interfaces:** none change. The props of `RichTextEditor` are identical.

- [ ] **Step 1: Write the failing test**

In `RichTextEditor.test.tsx`, append a new `describe` at the end of the file. It reuses the file's existing `beforeAll` jsdom shims:

```tsx
describe("RichTextEditor render cost", () => {
  it("does not call editor.setOptions when the parent re-renders with a new value/onChange", async () => {
    let editor: Editor | undefined;
    const { rerender } = render(
      <RichTextEditor value="<p>a</p>" onChange={() => {}} mode="rich" label="Body" onReady={(e) => (editor = e)} />
    );
    await waitFor(() => expect(editor).toBeDefined());
    const spy = vi.spyOn(editor!, "setOptions");
    for (const v of ["<p>ab</p>", "<p>abc</p>", "<p>abcd</p>"]) {
      rerender(
        <RichTextEditor value={v} onChange={() => {}} mode="rich" label="Body" onReady={(e) => (editor = e)} />
      );
    }
    expect(spy).not.toHaveBeenCalled();
  });

  it("still reconfigures when the placeholder changes", async () => {
    let editor: Editor | undefined;
    const onReady = (e: Editor) => (editor = e);
    const { rerender } = render(
      <RichTextEditor value="" onChange={() => {}} mode="rich" label="Body" placeholder="One" onReady={onReady} />
    );
    await waitFor(() => expect(editor).toBeDefined());
    const spy = vi.spyOn(editor!, "setOptions");
    rerender(
      <RichTextEditor value="" onChange={() => {}} mode="rich" label="Body" placeholder="Two" onReady={onReady} />
    );
    expect(spy).toHaveBeenCalled();
  });
});
```

`onReady` has a new identity on every rerender in the first test. That is intentional: `onReady` is not an editor option, so it must not trigger `setOptions`.

- [ ] **Step 2: Run the test and confirm the first one fails**

Run: `cd frontend && npx vitest run src/components/dashboard/rich-text/__tests__/RichTextEditor.test.tsx -t "render cost"`

Expected: the first test FAILS (`setOptions` called 3+ times). The second passes.

- [ ] **Step 3: Memoise the options**

In `RichTextEditor.tsx`:

- Change the react import to `import { useEffect, useId, useMemo, useRef, useState } from "react";`
- Before `const editor = useEditor({`, add:

```tsx
  // TipTap compares these by identity on every render and calls
  // editor.setOptions() (a full view update) when they differ, so they must be
  // stable. `content` is mount-time only: this component is uncontrolled.
  const [initialContent] = useState(() => fromStored(value, mode));
  const extensions = useMemo(
    () => (mode === "inline" ? inlineExtensions(placeholder) : richExtensions(placeholder)),
    [mode, placeholder]
  );
  const editorId = id ?? autoId;
  const editorProps = useMemo(
    () => ({
      attributes: {
        role: "textbox",
        "aria-multiline": mode === "rich" ? "true" : "false",
        "aria-label": label,
        id: editorId,
        class: `prose prose-sm prose-zinc dark:prose-invert max-w-none px-3 py-2 focus:outline-none ${
          mode === "rich" ? "min-h-[10rem]" : "min-h-[2.25rem]"
        }`,
      },
      transformPastedHTML: mode === "inline" ? inlinePaste : undefined,
      clipboardTextParser: mode === "inline" ? inlineClipboardTextParser : undefined,
      handleKeyDown: (_view: unknown, event: KeyboardEvent) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          setLinkOpen(true);
          return true;
        }
        return false;
      },
    }),
    [mode, label, editorId]
  );
```

Then change the `useEditor({...})` object to:

```tsx
  const editor = useEditor({
    extensions,
    content: initialContent,
    editable: !disabled,
    immediatelyRender: false,
    editorProps,
    onUpdate: ({ editor: e }) => {
      const stored = toStored(e.getHTML(), mode);
      setLength(stored.length);
      onChangeRef.current(stored);
    },
  });
```

If TypeScript complains about the `handleKeyDown` parameter types inside `useMemo`:

- Import `type EditorView` from `@tiptap/pm/view` and type `_view: EditorView`.
- Alternatively, annotate the memo result with `EditorOptions["editorProps"]` imported from `@tiptap/core`.

Keep the behaviour identical.

- [ ] **Step 4: Run the whole rich-text and editors suites**

Run: `cd frontend && npx vitest run src/components/dashboard/rich-text src/components/dashboard/editors && npx tsc --noEmit && npx eslint src/components/dashboard/rich-text/RichTextEditor.tsx`

Expected: all pass, including the existing 18 RichTextEditor cases (paste, link popover, Ctrl+K, no onChange on mount).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/rich-text/RichTextEditor.tsx frontend/src/components/dashboard/rich-text/__tests__/RichTextEditor.test.tsx
git commit -m "perf(rich-text): stable editor options so typing no longer reconfigures every editor"
```

---

### Task 9: Prefetch on hover — service cards and locale tabs

**Files:**
- Modify: `frontend/src/components/dashboard/ServiceCard.tsx`
- Modify: `frontend/src/components/dashboard/ServiceGrid.tsx`
- Modify: `frontend/src/components/dashboard/CmsSection.tsx`
- Modify: `frontend/src/components/dashboard/LocaleTabs.tsx`
- Modify: `frontend/src/components/dashboard/ServiceEditor.tsx`
- Test: `frontend/src/components/dashboard/__tests__/LocaleTabs.test.tsx`, `frontend/src/components/dashboard/__tests__/ServiceGrid.test.tsx`

**Interfaces:**
- Consumes (Task 6): `prefetchServiceDetail(projectSlug, serviceKey, locale?)`.
- Produces:
  - `ServiceCard` optional prop `onPrefetch?: () => void`
  - `ServiceGrid` optional prop `projectSlug?: string`
  - `LocaleTabs` optional prop `onPrefetch?: (locale: string) => void`

- [ ] **Step 1: Write the failing tests**

Append to `__tests__/LocaleTabs.test.tsx`. Add `vi`, `fireEvent` and `render`/`screen` to the imports if they are missing:

```tsx
describe("LocaleTabs prefetch", () => {
  it("prefetches a non-active locale on hover and focus, never the active one", () => {
    const onPrefetch = vi.fn();
    render(
      <LocaleTabs
        locales={["nl", "en"]}
        activeLocale="nl"
        defaultLocale="nl"
        onSelect={() => {}}
        onPrefetch={onPrefetch}
      />
    );
    fireEvent.mouseEnter(screen.getByRole("tab", { name: /en/i }));
    fireEvent.focus(screen.getByRole("tab", { name: /en/i }));
    fireEvent.mouseEnter(screen.getByRole("tab", { name: /nl/i }));
    expect(onPrefetch).toHaveBeenCalledWith("en");
    expect(onPrefetch).not.toHaveBeenCalledWith("nl");
  });
});
```

Append to `__tests__/ServiceGrid.test.tsx`. Open the file first and reuse its existing `next/navigation` mock and its sample services fixture; the variable name for the fixture varies, so use whatever that file defines:

First add, at the TOP of the file next to the other `vi.mock` calls, with the import placed with the other imports:

```tsx
vi.mock("../serviceApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../serviceApi")>()),
  prefetchServiceDetail: vi.fn(),
}));
import { prefetchServiceDetail } from "../serviceApi";
```

Then append:

```tsx
describe("ServiceGrid prefetch", () => {
  it("prefetches the service detail when hovering Edit", () => {
    const spy = vi.mocked(prefetchServiceDetail);
    spy.mockClear();
    render(
      <ServiceGrid
        services={SERVICES_FIXTURE}
        isAdmin={false}
        removingKey={null}
        onRemove={() => {}}
        projectSlug="demo"
      />
    );
    fireEvent.mouseEnter(screen.getAllByRole("link", { name: /edit/i })[0]);
    expect(spy).toHaveBeenCalledWith("demo", SERVICES_FIXTURE[0].service_key, undefined);
  });
});
```

Replace `SERVICES_FIXTURE` with the existing fixture name, and pick the fixture's first service that renders an **Edit** link on the default tab. If the default tab ordering means `[0]` is not the first rendered card, pick the service whose card is first. If the file has no fixture, define one with two `ServiceCardService` objects on page `"General"`, following the `ServiceCardService` interface in `ServiceCard.tsx`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/dashboard/__tests__/LocaleTabs.test.tsx src/components/dashboard/__tests__/ServiceGrid.test.tsx`

Expected: the new tests FAIL.

- [ ] **Step 3: Implement**

`LocaleTabs.tsx`:

- Add `onPrefetch?: (locale: string) => void;` to `LocaleTabsProps`, with the doc comment `/** Warm a locale's content on hover/focus so switching is instant. */`.
- Destructure it.
- On each `<button>`, add:

```tsx
            onMouseEnter={active ? undefined : () => onPrefetch?.(loc)}
            onFocus={active ? undefined : () => onPrefetch?.(loc)}
```

`ServiceCard.tsx`:

- Add `onPrefetch?: () => void;` to `ServiceCardProps`, with the comment `/** Warm the editor's data on hover/focus of Edit. */`.
- Destructure it.
- On the `<Link`, add `onMouseEnter={onPrefetch}` and `onFocus={onPrefetch}`.

`ServiceGrid.tsx`:

- Add `projectSlug?: string;` to `ServiceGridProps` and destructure it.
- Add `import { prefetchServiceDetail } from "@/components/dashboard/serviceApi";`.
- Inside the component, after `editHref`, add:

```tsx
  // The editor opens with the current `?locale=` (usually none → default).
  function prefetchFor(serviceKey: string) {
    if (!projectSlug) return undefined;
    return () =>
      prefetchServiceDetail(projectSlug, serviceKey, searchParams.get("locale") || undefined);
  }
```

- Pass `onPrefetch={prefetchFor(svc.service_key)}` to **both** `<ServiceCard` usages.

`CmsSection.tsx`: pass `projectSlug={projectSlug}` to `<ServiceGrid`.

`ServiceEditor.tsx`: pass this to `<LocaleTabs`:

```tsx
          onPrefetch={(loc) =>
            prefetchServiceDetail(projectSlug, serviceKey, loc === defaultLocale ? undefined : loc)
          }
```

This mirrors `setLocale`: the default locale has no `?locale=` param and therefore uses the key `…:default`. Make sure `prefetchServiceDetail` is in the serviceApi import.

- [ ] **Step 4: Run the tests, typecheck and lint**

Run: `cd frontend && npx vitest run src/components/dashboard && npx tsc --noEmit && npx eslint src/components/dashboard`

Expected: all pass and clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/ServiceCard.tsx frontend/src/components/dashboard/ServiceGrid.tsx frontend/src/components/dashboard/CmsSection.tsx frontend/src/components/dashboard/LocaleTabs.tsx frontend/src/components/dashboard/ServiceEditor.tsx frontend/src/components/dashboard/__tests__/LocaleTabs.test.tsx frontend/src/components/dashboard/__tests__/ServiceGrid.test.tsx
git commit -m "perf(dashboard): prefetch service content on hover of Edit and locale tabs"
```

---

### Task 10: Full gate, merge to dev, verify the region (controller runs this, not a subagent)

- [ ] **Step 1:** `make ci` from the repo root. It must be green. On Windows, if `make` is missing, run each target's commands from the `Makefile` by hand.
- [ ] **Step 2:** Run a whole-branch code review against the spec (superpowers:requesting-code-review), fix anything it confirms, then re-run `make ci`.
- [ ] **Step 3:** Delete `docs/superpowers/specs/2026-09-30-dashboard-speed-design.md` and this plan, per CLAUDE.md: they are temporary once the work is committed.
  - Commit: `docs: remove temporary dashboard-speed spec and plan`.
- [ ] **Step 4:** `git checkout dev && git merge --no-ff perf/dashboard-speed -m "Merge perf/dashboard-speed: dashboard speed" && git push origin dev`. This auto-deploys the Vercel previews.
- [ ] **Step 5:** Verify with the Vercel MCP `get_deployment` for the new preview deployments. Both must be READY, with regions `["dub1"]`.
- [ ] **Step 6:** Report the before and after numbers to the user. Promotion to production goes through "Promote dev → main".
