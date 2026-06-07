# Bookings Dashboard — Config & Provisioning (Phase 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a project owner a "Bookings" dashboard section to self-manage their booking config (settings, services, resources, hours+exceptions, policies), and an admin one-click "enable" that provisions a tenant — backed by new authenticated owner-facing FastAPI endpoints. No DB migration (reuses the Phase-1 schema).

**Architecture:** A new project-scoped router `booking_admin.py` (mirrors `issues.py`: `require_user` + `require_project_access(slug, user)` → `project["id"]` = `tenant_id`), reusing `booking_repo`/`booking_tenant` plus new owner CRUD helpers. The dashboard gains a `bookings` section gated by `bookingEnabled || isAdmin`, with an inner tab strip of focused config components mirroring `ProjectSettingsSection` (forms) and `LeadDetailDrawer` (list+detail).

**Tech Stack:** FastAPI + supabase-py service-role client (app-layer authz); Pydantic models; Next.js dashboard (`useQuery`/`cache`, `lib/styles.ts` primitives, `motion/react`); pytest + `TestClient`.

## Spec

Implements `docs/superpowers/specs/2026-06-05-booking-dashboard-config-design.md`. Read it first.

## Module map

| File | Responsibility | New/Modify |
|---|---|---|
| `backend/auth_service/models/booking_admin_schemas.py` | Pydantic request/response models for owner endpoints | Create |
| `backend/auth_service/services/booking_admin_repo.py` | Owner-side DB helpers (provision, CRUD, hours replace, slug-uniqueness, delete-guards) | Create |
| `backend/auth_service/routers/booking_admin.py` | Project-scoped owner endpoints (`/projects/{slug}/bookings/*`) | Create |
| `backend/auth_service/main.py` | Mount the new router | Modify |
| `backend/auth_service/tests/test_booking_admin_router.py` | Endpoint + ownership + provisioning tests | Create |
| `frontend/src/components/dashboard/sectionConfig.ts` | Add `bookings` section + capability gating | Modify |
| `frontend/src/app/dashboard/[projectSlug]/page.tsx` | Fetch `bookingEnabled`, pass caps, render `BookingsSection` | Modify |
| `frontend/src/components/dashboard/booking/BookingsSection.tsx` | Section shell: enable CTA or inner tab strip | Create |
| `frontend/src/components/dashboard/booking/BookingSettingsForm.tsx` | Settings form | Create |
| `frontend/src/components/dashboard/booking/ServicesManager.tsx` + `ServiceFormDrawer.tsx` | Services list + add/edit drawer | Create |
| `frontend/src/components/dashboard/booking/ResourcesManager.tsx` + `ResourceFormDrawer.tsx` | Resources list + add/edit drawer | Create |
| `frontend/src/components/dashboard/booking/HoursEditor.tsx` | Weekly hours grid + closed-dates | Create |
| `frontend/src/components/dashboard/booking/PoliciesForm.tsx` | Policy windows/limits/text | Create |
| `frontend/src/components/dashboard/booking/api.ts` | Typed fetch helpers + types for the booking-admin endpoints | Create |

---

# PART A — Backend owner endpoints

## Task A1: Pydantic models

**Files:** Create `backend/auth_service/models/booking_admin_schemas.py`

- [ ] **Step 1: Write the models**

```python
"""Request/response models for the owner-facing booking config API (Phase 2a)."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsPatch(BaseModel):
    timezone: str | None = None
    locale: str | None = None
    business_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    email_from_name: str | None = None
    owner_notification_email: str | None = None
    meeting_url: str | None = None
    slot_granularity_min: int | None = None
    reminders_enabled: bool | None = None
    reminder_offsets_min: list[int] | None = None
    calendar_provider: str | None = None
    public_slug: str | None = None


class ServiceIn(BaseModel):
    name: str
    description: str = ""
    color: str = ""
    duration_min: int
    buffer_before_min: int = 0
    buffer_after_min: int = 0
    lead_time_min: int = 0
    max_advance_days: int = 60
    is_active: bool = True
    sort_order: int = 0
    resource_ids: list[str] = []


class ResourceIn(BaseModel):
    name: str
    type: str = "generic"
    capacity: int = 1
    is_active: bool = True
    sort_order: int = 0


class HoursRow(BaseModel):
    resource_id: str | None = None
    weekday: int   # 0=Sun .. 6=Sat
    start_time: str  # "HH:MM"
    end_time: str


class HoursReplace(BaseModel):
    hours: list[HoursRow]


class ExceptionIn(BaseModel):
    resource_id: str | None = None
    date: str        # "YYYY-MM-DD"
    is_closed: bool = True
    start_time: str | None = None
    end_time: str | None = None


class PolicyPatch(BaseModel):
    service_id: str | None = None  # null = tenant default
    allow_reschedule: bool = True
    reschedule_window_hours: int = 24
    max_reschedules: int = 2
    allow_cancel: bool = True
    cancellation_window_hours: int = 24
    policy_text: str = ""
```

- [ ] **Step 2: Verify import**

Run: `cd backend && source venv/Scripts/activate && python -c "from auth_service.models.booking_admin_schemas import SettingsPatch, ServiceIn, HoursReplace; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit** (skipped per no-auto-commit; controller leaves in working tree)

## Task A2: Owner repo helpers

**Files:** Create `backend/auth_service/services/booking_admin_repo.py`; Test `backend/auth_service/tests/test_booking_admin_repo.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import MagicMock, patch

from auth_service.services import booking_admin_repo


def _sb():
    sb = MagicMock()
    for m in ["table", "select", "insert", "update", "upsert", "delete", "eq",
              "neq", "in_", "is_", "limit", "order", "maybe_single"]:
        getattr(sb, m).return_value = sb
    return sb


def _exec(sb, data):
    sb.execute.return_value = type("R", (), {"data": data})()
    return sb


def test_get_settings_returns_none_when_absent():
    sb = _exec(_sb(), [])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.get_settings("t1") is None


def test_slug_taken_by_other_detects_clash():
    sb = _exec(_sb(), [{"tenant_id": "other"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.slug_taken_by_other("acme", "t1") is True


def test_slug_taken_by_other_false_for_self():
    sb = _exec(_sb(), [{"tenant_id": "t1"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.slug_taken_by_other("acme", "t1") is False


def test_resource_has_bookings_true():
    sb = _exec(_sb(), [{"id": "b1"}])
    with patch("auth_service.services.booking_admin_repo.get_supabase_admin", return_value=sb):
        assert booking_admin_repo.resource_has_bookings("t1", "r1") is True
```

- [ ] **Step 2: Run → fails** (`ModuleNotFoundError`). Run: `cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_booking_admin_repo.py -v`

- [ ] **Step 3: Write the implementation**

```python
"""Owner-side booking config DB helpers (Phase 2a). Service-role client;
caller passes an explicit tenant_id (= project id) for every operation."""

from __future__ import annotations

from datetime import UTC, datetime

from .supabase_client import get_supabase_admin

_DEFAULT_RESOURCE = "00000000-0000-0000-0000-000000000000"  # placeholder, unused


def get_settings(tenant_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("booking_settings").select("*").eq("tenant_id", tenant_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def slug_taken_by_other(public_slug: str, tenant_id: str) -> bool:
    sb = get_supabase_admin()
    res = (sb.table("booking_settings").select("tenant_id")
           .eq("public_slug", public_slug).limit(1).execute())
    rows = res.data or []
    return bool(rows) and rows[0]["tenant_id"] != tenant_id


def update_settings(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    fields = {**fields, "updated_at": datetime.now(UTC).isoformat()}
    res = sb.table("booking_settings").update(fields).eq("tenant_id", tenant_id).execute()
    return (res.data or [{}])[0]


def provision(*, tenant_id: str, public_slug: str, business_name: str,
              owner_email: str, timezone: str = "Europe/Berlin") -> dict:
    """Idempotent: create booking_settings + default resource/service/hours/policy
    if the tenant has no settings row yet. Returns the settings row."""
    sb = get_supabase_admin()
    existing = get_settings(tenant_id)
    if existing:
        return existing
    settings_row = sb.table("booking_settings").insert({
        "tenant_id": tenant_id, "public_slug": public_slug, "timezone": timezone,
        "locale": "en", "business_name": business_name,
        "owner_notification_email": owner_email, "email_from_name": business_name,
        "calendar_provider": "none", "reminder_offsets_min": [1440, 120],
    }).execute().data[0]
    resource = sb.table("booking_resources").insert({
        "tenant_id": tenant_id, "name": "Staff", "type": "staff",
    }).execute().data[0]
    service = sb.table("booking_services").insert({
        "tenant_id": tenant_id, "name": "Consultation", "duration_min": 30,
        "lead_time_min": 120, "max_advance_days": 60,
    }).execute().data[0]
    sb.table("booking_service_resources").insert({
        "tenant_id": tenant_id, "service_id": service["id"], "resource_id": resource["id"],
    }).execute()
    sb.table("booking_hours").insert([
        {"tenant_id": tenant_id, "resource_id": None, "weekday": d,
         "start_time": "09:00", "end_time": "17:00"} for d in (1, 2, 3, 4, 5)
    ]).execute()
    sb.table("booking_policies").insert({
        "tenant_id": tenant_id, "service_id": None,
        "policy_text": "Reschedule up to 24h before; cancel up to 24h before.",
    }).execute()
    return settings_row


# ---- services ----
def list_services(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_services").select("*").eq("tenant_id", tenant_id)
            .order("sort_order").execute()).data or []


def list_service_resource_links(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_service_resources").select("service_id, resource_id")
            .eq("tenant_id", tenant_id).execute()).data or []


def insert_service(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return sb.table("booking_services").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def update_service(tenant_id: str, service_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    res = (sb.table("booking_services").update(fields)
           .eq("tenant_id", tenant_id).eq("id", service_id).execute())
    return (res.data or [{}])[0]


def set_service_resources(tenant_id: str, service_id: str, resource_ids: list[str]) -> None:
    sb = get_supabase_admin()
    sb.table("booking_service_resources").delete().eq("tenant_id", tenant_id).eq(
        "service_id", service_id).execute()
    if resource_ids:
        sb.table("booking_service_resources").insert([
            {"tenant_id": tenant_id, "service_id": service_id, "resource_id": rid}
            for rid in resource_ids
        ]).execute()


def service_has_bookings(tenant_id: str, service_id: str) -> bool:
    sb = get_supabase_admin()
    res = (sb.table("bookings").select("id").eq("tenant_id", tenant_id)
           .eq("service_id", service_id).limit(1).execute())
    return bool(res.data)


def delete_service(tenant_id: str, service_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_services").delete().eq("tenant_id", tenant_id).eq("id", service_id).execute()


# ---- resources ----
def list_resources(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_resources").select("*").eq("tenant_id", tenant_id)
            .order("sort_order").execute()).data or []


def insert_resource(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return sb.table("booking_resources").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def update_resource(tenant_id: str, resource_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    res = (sb.table("booking_resources").update(fields)
           .eq("tenant_id", tenant_id).eq("id", resource_id).execute())
    return (res.data or [{}])[0]


def resource_has_bookings(tenant_id: str, resource_id: str) -> bool:
    sb = get_supabase_admin()
    res = (sb.table("bookings").select("id").eq("tenant_id", tenant_id)
           .eq("resource_id", resource_id).limit(1).execute())
    return bool(res.data)


def delete_resource(tenant_id: str, resource_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_resources").delete().eq("tenant_id", tenant_id).eq("id", resource_id).execute()


# ---- hours ----
def list_hours(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_hours").select("*").eq("tenant_id", tenant_id).execute()).data or []


def replace_hours(tenant_id: str, rows: list[dict]) -> None:
    sb = get_supabase_admin()
    sb.table("booking_hours").delete().eq("tenant_id", tenant_id).execute()
    if rows:
        sb.table("booking_hours").insert(
            [{**r, "tenant_id": tenant_id} for r in rows]).execute()


# ---- exceptions ----
def list_exceptions(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_exceptions").select("*").eq("tenant_id", tenant_id)
            .order("date").execute()).data or []


def insert_exception(tenant_id: str, fields: dict) -> dict:
    sb = get_supabase_admin()
    return sb.table("booking_exceptions").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def delete_exception(tenant_id: str, exc_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("booking_exceptions").delete().eq("tenant_id", tenant_id).eq("id", exc_id).execute()


# ---- policies ----
def list_policies(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    return (sb.table("booking_policies").select("*").eq("tenant_id", tenant_id).execute()).data or []


def upsert_policy(tenant_id: str, fields: dict) -> dict:
    """Upsert by (tenant_id, service_id-or-null). Delete-then-insert the matching
    scope to avoid relying on a partial unique index through PostgREST."""
    sb = get_supabase_admin()
    service_id = fields.get("service_id")
    q = sb.table("booking_policies").delete().eq("tenant_id", tenant_id)
    q = q.is_("service_id", "null") if service_id is None else q.eq("service_id", service_id)
    q.execute()
    return sb.table("booking_policies").insert({**fields, "tenant_id": tenant_id}).execute().data[0]


def owner_email(user_id: str) -> str:
    sb = get_supabase_admin()
    res = sb.table("users").select("email").eq("id", user_id).limit(1).execute()
    rows = res.data or []
    return rows[0]["email"] if rows else ""
```

- [ ] **Step 4: Run → 4 passed.**
- [ ] **Step 5: Commit** (skipped per no-auto-commit)

## Task A3: The router

**Files:** Create `backend/auth_service/routers/booking_admin.py`; Modify `backend/auth_service/main.py`; Test `backend/auth_service/tests/test_booking_admin_router.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
ADMIN = UserOut(id="admin", email="a@x.com", full_name="A", is_admin=True)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}


@pytest.fixture
def client():
    return TestClient(app)


def _auth(user, project=PROJECT):
    # require_user and require_project_access are imported INTO booking_admin, patch there.
    return (
        patch("auth_service.routers.booking_admin.require_user", return_value=user),
        patch("auth_service.routers.booking_admin.require_project_access", return_value=project),
    )


def test_get_settings_disabled_when_absent(client):
    ru, rp = _auth(OWNER)
    with ru, rp, patch("auth_service.routers.booking_admin.booking_admin_repo.get_settings", return_value=None):
        r = client.get("/projects/acme/bookings/settings")
    assert r.status_code == 200 and r.json() == {"enabled": False}


def test_get_settings_enabled(client):
    ru, rp = _auth(OWNER)
    row = {"tenant_id": "t1", "public_slug": "acme", "timezone": "Europe/Berlin"}
    with ru, rp, patch("auth_service.routers.booking_admin.booking_admin_repo.get_settings", return_value=row):
        r = client.get("/projects/acme/bookings/settings")
    body = r.json()
    assert body["enabled"] is True and body["public_slug"] == "acme"


def test_enable_requires_admin(client):
    # Non-admin → 403 from admin_user_via_bearer_or_sid (patch it to raise).
    from fastapi import HTTPException
    with patch("auth_service.routers.booking_admin.admin_user_via_bearer_or_sid",
               side_effect=HTTPException(status_code=403, detail="Admin access required")):
        r = client.post("/projects/acme/bookings/enable")
    assert r.status_code == 403


def test_enable_provisions(client):
    ru, rp = _auth(ADMIN)
    with (
        patch("auth_service.routers.booking_admin.admin_user_via_bearer_or_sid", return_value=ADMIN),
        rp,
        patch("auth_service.routers.booking_admin.booking_admin_repo.owner_email", return_value="o@acme.com"),
        patch("auth_service.routers.booking_admin.booking_admin_repo.provision",
              return_value={"tenant_id": "t1", "public_slug": "acme"}) as prov,
    ):
        r = client.post("/projects/acme/bookings/enable")
    assert r.status_code == 200 and r.json()["enabled"] is True
    prov.assert_called_once()


def test_patch_settings_slug_clash_409(client):
    ru, rp = _auth(OWNER)
    with (
        ru, rp,
        patch("auth_service.routers.booking_admin.booking_admin_repo.slug_taken_by_other", return_value=True),
    ):
        r = client.patch("/projects/acme/bookings/settings", json={"public_slug": "taken"})
    assert r.status_code == 409


def test_services_crud_roundtrip(client):
    ru, rp = _auth(OWNER)
    with (
        ru, rp,
        patch("auth_service.routers.booking_admin.booking_admin_repo.insert_service",
              return_value={"id": "s1", "name": "Cut"}),
        patch("auth_service.routers.booking_admin.booking_admin_repo.set_service_resources"),
    ):
        r = client.post("/projects/acme/bookings/services",
                        json={"name": "Cut", "duration_min": 45, "resource_ids": ["r1"]})
    assert r.status_code == 201 and r.json()["id"] == "s1"


def test_delete_service_blocked_when_referenced(client):
    ru, rp = _auth(OWNER)
    with (
        ru, rp,
        patch("auth_service.routers.booking_admin.booking_admin_repo.service_has_bookings", return_value=True),
    ):
        r = client.delete("/projects/acme/bookings/services/s1")
    assert r.status_code == 409


def test_isolation_other_owner_403(client):
    from fastapi import HTTPException
    with (
        patch("auth_service.routers.booking_admin.require_user", return_value=OWNER),
        patch("auth_service.routers.booking_admin.require_project_access",
              side_effect=HTTPException(status_code=403, detail="Access denied")),
    ):
        r = client.get("/projects/someone-else/bookings/settings")
    assert r.status_code == 403
```

- [ ] **Step 2: Run → fails** (router not mounted / not found).

- [ ] **Step 3: Write the router**

```python
"""Owner-facing booking config API (Phase 2a). Project-scoped; mirrors issues.py.
Auth: session → require_user → require_project_access (owner-or-admin) →
project['id'] is the booking tenant_id. `enable` additionally requires admin."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..models.booking_admin_schemas import (
    ExceptionIn, HoursReplace, PolicyPatch, ResourceIn, ServiceIn, SettingsPatch,
)
from ..services import booking_admin_repo
from .deps import admin_user_via_bearer_or_sid, require_project_access, require_user

router = APIRouter(tags=["booking-admin"])


async def _tenant(project_slug: str, request: Request) -> str:
    user = await require_user(request)
    project = require_project_access(project_slug, user)
    return project["id"]


@router.get("/projects/{project_slug}/bookings/settings")
async def get_settings(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.get_settings(tenant_id)
    if not row:
        return JSONResponse(content={"enabled": False})
    return JSONResponse(content={"enabled": True, **row})


@router.post("/projects/{project_slug}/bookings/enable")
async def enable(project_slug: str, request: Request) -> JSONResponse:
    admin = await admin_user_via_bearer_or_sid(request)  # admin-only (raises 403 otherwise)
    project = require_project_access(project_slug, admin)
    owner = booking_admin_repo.owner_email(project["user_id"]) or admin.email
    row = booking_admin_repo.provision(
        tenant_id=project["id"], public_slug=project["slug"],
        business_name=project["name"], owner_email=owner)
    return JSONResponse(content={"enabled": True, **row})


@router.patch("/projects/{project_slug}/bookings/settings")
async def patch_settings(project_slug: str, body: SettingsPatch, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if "public_slug" in fields and booking_admin_repo.slug_taken_by_other(fields["public_slug"], tenant_id):
        raise HTTPException(status_code=409, detail="That public link is already taken")
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")
    return JSONResponse(content=booking_admin_repo.update_settings(tenant_id, fields))


# ---- services ----
@router.get("/projects/{project_slug}/bookings/services")
async def list_services(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    services = booking_admin_repo.list_services(tenant_id)
    links = booking_admin_repo.list_service_resource_links(tenant_id)
    by_service: dict[str, list[str]] = {}
    for link in links:
        by_service.setdefault(link["service_id"], []).append(link["resource_id"])
    for s in services:
        s["resource_ids"] = by_service.get(s["id"], [])
    return JSONResponse(content={"services": services})


@router.post("/projects/{project_slug}/bookings/services", status_code=status.HTTP_201_CREATED)
async def create_service(project_slug: str, body: ServiceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    fields = body.model_dump(exclude={"resource_ids"})
    row = booking_admin_repo.insert_service(tenant_id, fields)
    booking_admin_repo.set_service_resources(tenant_id, row["id"], body.resource_ids)
    return JSONResponse(content={**row, "resource_ids": body.resource_ids},
                        status_code=status.HTTP_201_CREATED)


@router.patch("/projects/{project_slug}/bookings/services/{service_id}")
async def patch_service(project_slug: str, service_id: str, body: ServiceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    fields = body.model_dump(exclude={"resource_ids"})
    row = booking_admin_repo.update_service(tenant_id, service_id, fields)
    booking_admin_repo.set_service_resources(tenant_id, service_id, body.resource_ids)
    return JSONResponse(content={**row, "resource_ids": body.resource_ids})


@router.delete("/projects/{project_slug}/bookings/services/{service_id}")
async def delete_service(project_slug: str, service_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    if booking_admin_repo.service_has_bookings(tenant_id, service_id):
        raise HTTPException(status_code=409, detail="Service has bookings; deactivate it instead")
    booking_admin_repo.delete_service(tenant_id, service_id)
    return JSONResponse(content={"deleted": True})


# ---- resources ----
@router.get("/projects/{project_slug}/bookings/resources")
async def list_resources(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content={"resources": booking_admin_repo.list_resources(tenant_id)})


@router.post("/projects/{project_slug}/bookings/resources", status_code=status.HTTP_201_CREATED)
async def create_resource(project_slug: str, body: ResourceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.insert_resource(tenant_id, body.model_dump())
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.patch("/projects/{project_slug}/bookings/resources/{resource_id}")
async def patch_resource(project_slug: str, resource_id: str, body: ResourceIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content=booking_admin_repo.update_resource(tenant_id, resource_id, body.model_dump()))


@router.delete("/projects/{project_slug}/bookings/resources/{resource_id}")
async def delete_resource(project_slug: str, resource_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    if booking_admin_repo.resource_has_bookings(tenant_id, resource_id):
        raise HTTPException(status_code=409, detail="Resource has bookings; deactivate it instead")
    booking_admin_repo.delete_resource(tenant_id, resource_id)
    return JSONResponse(content={"deleted": True})


# ---- hours + exceptions ----
@router.get("/projects/{project_slug}/bookings/hours")
async def get_hours(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content={
        "hours": booking_admin_repo.list_hours(tenant_id),
        "exceptions": booking_admin_repo.list_exceptions(tenant_id),
    })


@router.put("/projects/{project_slug}/bookings/hours")
async def put_hours(project_slug: str, body: HoursReplace, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    rows = []
    for h in body.hours:
        if not (0 <= h.weekday <= 6) or h.start_time >= h.end_time:
            raise HTTPException(status_code=422, detail="Invalid hours interval")
        rows.append({"resource_id": h.resource_id, "weekday": h.weekday,
                     "start_time": h.start_time, "end_time": h.end_time})
    booking_admin_repo.replace_hours(tenant_id, rows)
    return JSONResponse(content={"hours": booking_admin_repo.list_hours(tenant_id)})


@router.post("/projects/{project_slug}/bookings/exceptions", status_code=status.HTTP_201_CREATED)
async def create_exception(project_slug: str, body: ExceptionIn, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.insert_exception(tenant_id, body.model_dump())
    return JSONResponse(content=row, status_code=status.HTTP_201_CREATED)


@router.delete("/projects/{project_slug}/bookings/exceptions/{exc_id}")
async def delete_exception(project_slug: str, exc_id: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    booking_admin_repo.delete_exception(tenant_id, exc_id)
    return JSONResponse(content={"deleted": True})


# ---- policies ----
@router.get("/projects/{project_slug}/bookings/policies")
async def get_policies(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content={"policies": booking_admin_repo.list_policies(tenant_id)})


@router.patch("/projects/{project_slug}/bookings/policies")
async def patch_policy(project_slug: str, body: PolicyPatch, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    return JSONResponse(content=booking_admin_repo.upsert_policy(tenant_id, body.model_dump()))
```

- [ ] **Step 4: Mount in `main.py`** — add import beside the booking import (main.py:24) and an `include_router` beside it (main.py:142):

```python
from .routers.booking_admin import router as booking_admin_router  # noqa: E402
```
```python
app.include_router(booking_admin_router)
```

- [ ] **Step 5: Run → all pass.** Run: `cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_booking_admin_router.py auth_service/tests/test_booking_admin_repo.py -v`

- [ ] **Step 6: Full backend suite stays green.** Run: `pytest auth_service/tests/ -q`

- [ ] **Step 7: Commit** (skipped per no-auto-commit)

---

# PART B — Frontend dashboard section

## Task B1: Typed API helpers

**Files:** Create `frontend/src/components/dashboard/booking/api.ts`

- [ ] **Step 1:** Create the module with types + thin fetch wrappers. Each wrapper hits `/api/projects/${slug}/bookings/...` with `credentials: "include"` and throws `Error(detail)` on non-ok (mirrors `useLeadPatch`). Types: `BookingSettings`, `BookingService`, `BookingResource`, `BookingHour`, `BookingException`, `BookingPolicy`. Functions: `getSettings(slug)`, `enableBookings(slug)`, `patchSettings(slug, body)`, `listServices(slug)`, `createService(slug, body)`, `patchService(slug, id, body)`, `deleteService(slug, id)`, and the resource / hours (`getHours`, `putHours`) / exception (`createException`, `deleteException`) / policy (`getPolicies`, `patchPolicy`) equivalents. Shape the request/response types to match Part A's models exactly (field names identical).

```typescript
// Representative wrapper (replicate the pattern for every endpoint):
export async function patchSettings(slug: string, body: Partial<BookingSettings>): Promise<BookingSettings> {
  const r = await fetch(`/api/projects/${slug}/bookings/settings`, {
    method: "PATCH", credentials: "include",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Save failed");
  return r.json();
}
```

- [ ] **Step 2: Verify** typecheck after the section is wired (Task B6).

## Task B2: Section gating

**Files:** Modify `frontend/src/components/dashboard/sectionConfig.ts`

- [ ] **Step 1: Replace the file with:**

```typescript
import { LayoutDashboard, FileText, LocateFixed, Settings, Calendar, type LucideIcon } from "lucide-react";

export type SectionKey = "dashboard" | "cms" | "autofix" | "bookings" | "settings";

export interface SectionCaps {
  bookingEnabled: boolean;
}

export interface SectionDef {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  /** Section is shown only when this capability is true (admins always see it). */
  requiresCap?: keyof SectionCaps;
}

export const PROJECT_SECTIONS: SectionDef[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "cms", label: "CMS", icon: FileText },
  { key: "autofix", label: "Auto-Fix", icon: LocateFixed },
  { key: "bookings", label: "Bookings", icon: Calendar, requiresCap: "bookingEnabled" },
  { key: "settings", label: "Settings", icon: Settings, adminOnly: true },
];

export const DEFAULT_VIEW: SectionKey = "dashboard";

export function visibleSections(isAdmin: boolean, caps: SectionCaps = { bookingEnabled: false }): SectionDef[] {
  return PROJECT_SECTIONS.filter((s) => {
    if (s.adminOnly && !isAdmin) return false;
    if (s.requiresCap && !caps[s.requiresCap] && !isAdmin) return false;
    return true;
  });
}

export function isAccessibleView(view: string | null, isAdmin: boolean, caps?: SectionCaps): view is SectionKey {
  return view !== null && visibleSections(isAdmin, caps).some((s) => s.key === view);
}
```

- [ ] **Step 2:** Check callers of `visibleSections`/`isAccessibleView` (the `useProjectView` hook + the page) still compile — they pass the new optional `caps`; update those call sites in Task B3.

## Task B3: Page wiring

**Files:** Modify `frontend/src/app/dashboard/[projectSlug]/page.tsx`

- [ ] **Step 1:** Add a `useQuery` for booking-enabled and pass caps through. Near the other section state:

```typescript
import { getSettings } from "@/components/dashboard/booking/api";
// ...
const { data: bookingSettings } = useQuery(
  `booking-settings:${projectSlug}`,
  () => getSettings(projectSlug),
  { ttl: 60 * 1000 }
);
const caps = { bookingEnabled: !!bookingSettings?.enabled };
const sections = visibleSections(isAdmin, caps);
```

Pass `caps` to `useProjectView` / `isAccessibleView` where the active view is validated (so `?view=bookings` is gated). Add to the `SectionPanel` switch:

```typescript
{activeView === "bookings" && <BookingsSection projectSlug={projectSlug} isAdmin={isAdmin} />}
```

- [ ] **Step 2:** Update the `useProjectView` hook (`frontend/src/components/dashboard/hooks/useProjectView.ts`) to accept and forward `caps` to `isAccessibleView` (read the file; thread the param). Keep its default so other callers compile.

## Task B4: BookingsSection shell

**Files:** Create `frontend/src/components/dashboard/booking/BookingsSection.tsx`

- [ ] **Step 1:** Build the shell. Props `{ projectSlug: string; isAdmin: boolean }`. `useQuery('booking-settings:'+slug, () => getSettings(slug))`. If `loading` → skeleton. If `!data.enabled`:
  - admin → a card with copy "Bookings isn't enabled for this project." + an "Enable bookings" button that calls `enableBookings(slug)`, invalidates the `booking-settings:` cache key, and re-renders.
  - non-admin → a neutral "Bookings aren't enabled yet — contact your administrator." card.
  If enabled → render an inner tab strip (local `useState<"settings"|"services"|"resources"|"hours"|"policies">`) of buttons styled like a secondary nav, and below it the active child component, each receiving `{ projectSlug }` (and `services`/`resources` where needed). Use `dashboardSectionCardCn` for cards and the `.cursor-pointer` rule on buttons.

## Task B5: Config child components

**Files:** Create `BookingSettingsForm.tsx`, `ServicesManager.tsx`, `ServiceFormDrawer.tsx`, `ResourcesManager.tsx`, `ResourceFormDrawer.tsx`, `HoursEditor.tsx`, `PoliciesForm.tsx` under `frontend/src/components/dashboard/booking/`

Each mirrors an established component; build them to these contracts (data via Task B1 `api.ts`; styling via `lib/styles.ts`; feedback via the success/error banner pattern from `ProjectSettingsSection`):

- [ ] **BookingSettingsForm** — mirror `ProjectSettingsSection.tsx`. Draft state from `getSettings`; fields: business_name, timezone (text or select), locale, public_slug, owner_notification_email, meeting_url, email_from_name, primary_color, accent_color, logo_url, slot_granularity_min, reminders_enabled (toggle), reminder_offsets_min (comma input → int[]), calendar_provider (select none/google). Save via `patchSettings`; show 409 slug-clash inline; success/error banner.
- [ ] **ServicesManager** + **ServiceFormDrawer** — mirror `AutoFixSection` (list + add) + `LeadDetailDrawer` (edit drawer). List from `listServices`. Drawer form fields: name, duration_min, buffer_before_min, buffer_after_min, lead_time_min, max_advance_days, color, is_active, and a resource multiselect (from `listResources`) → `resource_ids`. Create via `createService`, edit via `patchService`, delete via `deleteService` (surface the 409 "has bookings" message). Refresh-trigger pattern after mutations.
- [ ] **ResourcesManager** + **ResourceFormDrawer** — same pattern; fields: name, type (select staff/room/equipment/generic), capacity, is_active, sort_order. `createResource`/`patchResource`/`deleteResource` (409 guard).
- [ ] **HoursEditor** — `getHours` → render 7 weekday rows (Sun..Sat), each with zero-or-more `{start_time,end_time}` intervals (add/remove). A "Save hours" button builds the flat `HoursРow[]` (business-level `resource_id: null`) and calls `putHours`. Below, a "Closed dates" panel: list exceptions, add (date + is_closed), delete — via `createException`/`deleteException`. Inline 422 on invalid interval.
- [ ] **PoliciesForm** — `getPolicies` → edit the tenant-default policy (service_id null): allow_reschedule, reschedule_window_hours, max_reschedules, allow_cancel, cancellation_window_hours, policy_text (textarea) with a live preview box. Save via `patchPolicy`.

## Task B6: Verify frontend

- [ ] **Step 1:** `cd frontend && npm run typecheck` (or `npx tsc --noEmit`) → clean. Fix any type mismatches against `api.ts`.
- [ ] **Step 2:** `cd frontend && npm run lint` if configured → clean.
- [ ] **Step 3 (milestone build):** `cd frontend && npm run build` → succeeds. (Per the no-build-after-every-change rule, build once here at the milestone.)

---

## Done criteria (Phase 2a)

- New `booking_admin` router mounted; owner-scoped CRUD for settings/services/resources/hours/exceptions/policies + admin `enable`; backend suite green; ownership + isolation + provisioning + slug-clash + delete-guard tested.
- Dashboard "Bookings" section appears for enabled projects (and admins), with the five config tabs; admin can enable a project in one click; owner self-manages. Typecheck + build clean.
- No DB migration. Nothing committed (per the no-auto-commit rule). Appointments (2b), Overview/stats (2c), and the Embed page (P3) remain.
