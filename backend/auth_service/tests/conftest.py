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
    for method in ["table", "select", "eq", "in_", "order", "limit", "single", "insert",
                   "upsert", "update", "delete", "neq", "filter"]:
        getattr(mock, method).return_value = mock

    # Each patch wrapped in try/except so early tasks can run before later
    # modules (e.g. publish.py in Task 7) exist. Includes get_supabase_admin
    # because workspace.py uses it for file upload + client account creation —
    # an untrapped admin call would silently hit a real DB in tests.
    targets = [
        "auth_service.routers.content.get_supabase",
        "auth_service.routers.workspace.get_supabase",
        "auth_service.routers.workspace.get_supabase_admin",
        "auth_service.routers.projects.get_supabase",
        "auth_service.routers.publish.get_supabase",  # created in Task 7
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
