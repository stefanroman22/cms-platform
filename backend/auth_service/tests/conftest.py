from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ..models.schemas import UserOut


@pytest.fixture
def mock_supabase():
    """Patches get_supabase_admin() everywhere it's imported.

    The returned MagicMock mimics the chained supabase-py builder; individual
    tests override .execute() return values per-call.
    """
    mock = MagicMock()
    # Make every builder method return the mock itself so chains like
    # .table().select().eq().single().execute() all work.
    for method in [
        "table",
        "select",
        "eq",
        "in_",
        "order",
        "limit",
        "single",
        "maybe_single",
        "insert",
        "upsert",
        "update",
        "delete",
        "neq",
        "filter",
    ]:
        getattr(mock, method).return_value = mock

    # Each patch wrapped in try/except so early tasks can run before later
    # modules (e.g. publish.py in Task 7) exist. Includes get_supabase_admin
    # because workspace.py uses it for file upload + client account creation —
    # an untrapped admin call would silently hit a real DB in tests.
    targets = [
        "auth_service.routers.content.get_supabase_admin",
        "auth_service.routers.workspace.get_supabase_admin",
        "auth_service.routers.workspace.get_supabase_admin",
        "auth_service.routers.projects.get_supabase_admin",
        "auth_service.routers.publish.get_supabase_admin",  # created in Task 7
        "auth_service.services.sessions.get_supabase_admin",
        # auth.change_password does `from ..services.supabase_client import get_supabase_admin`
        # inline — patch the source so the late import sees the mock.
        "auth_service.services.supabase_client.get_supabase_admin",
    ]
    started = []
    try:
        for target in targets:
            try:
                p = patch(target, return_value=mock)
                p.start()
                started.append(p)
            except (ModuleNotFoundError, AttributeError):
                continue
        yield mock
    finally:
        for p in started:
            p.stop()


@pytest.fixture
def client():
    # Import lazily — the app graph currently fails to import on this branch
    # (Task 1 stripped JWT helpers still referenced by services.auth_service).
    # Tests that don't need the HTTP client (e.g. test_sessions.py) should not
    # pay that cost.
    from ..main import app

    return TestClient(app)


@pytest.fixture
def admin_user():
    return UserOut(id="admin-uuid", email="admin@example.com", full_name="Admin", is_admin=True)


@pytest.fixture
def client_user():
    return UserOut(
        id="client-uuid", email="laurian@example.com", full_name="Laurian", is_admin=False
    )


@pytest.fixture
def auth_as(monkeypatch):
    """Call `auth_as(user)` inside a test to bypass cookie auth with the given user."""

    def _apply(user: UserOut):
        async def fake_require_user(request):
            return user

        # Patch every router's require_user import site
        monkeypatch.setattr("auth_service.routers.workspace.require_user", fake_require_user)
        # The shared admin_user_via_bearer_or_sid dep calls require_user directly
        # from the deps module — patch it there too so the fake user reaches the
        # admin-gated routes refactored in Task 3.
        monkeypatch.setattr("auth_service.routers.deps.require_user", fake_require_user)
        # projects.py uses a private _require_user that doesn't import from deps — skip safely
        try:
            monkeypatch.setattr("auth_service.routers.projects.require_user", fake_require_user)
        except (AttributeError, ModuleNotFoundError, ImportError):
            pass
        # publish.py — added in Task 9, but the patch is idempotent (AttributeError caught)
        try:
            monkeypatch.setattr("auth_service.routers.publish.require_user", fake_require_user)
        except (AttributeError, ModuleNotFoundError, ImportError):
            pass

        def fake_require_project_access(slug, u):
            return {"id": f"project-{slug}", "slug": slug, "name": slug.title()}

        monkeypatch.setattr(
            "auth_service.routers.workspace.require_project_access", fake_require_project_access
        )
        try:
            monkeypatch.setattr(
                "auth_service.routers.publish.require_project_access", fake_require_project_access
            )
        except (AttributeError, ModuleNotFoundError, ImportError):
            pass

    return _apply
