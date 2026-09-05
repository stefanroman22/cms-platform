# backend/auth_service/tests/test_seo_router.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

client = TestClient(app)


def _auth(monkeypatch, admin=True):
    async def fake(request):
        return UserOut(id="u1", email="a@b.com", is_admin=admin)

    monkeypatch.setattr("auth_service.routers.seo.user_via_bearer_or_session", fake)
    monkeypatch.setattr(
        "auth_service.routers.seo.require_project_access",
        lambda slug, u: {
            "id": f"proj-{slug}",
            "slug": slug,
            "name": slug.title(),
            "locales": ["en", "nl"],
        },
    )


def test_overview_empty(monkeypatch):
    _auth(monkeypatch)
    with (
        patch("auth_service.routers.seo.seo_repo.latest_run", return_value=None),
        patch("auth_service.routers.seo.seo_repo.latest_audit", return_value=None),
        patch(
            "auth_service.routers.seo._project_flags",
            return_value={"seo_enabled": False, "seo_blog_route": None, "seo_last_run_at": None},
        ),
    ):
        r = client.get("/projects/acme/seo/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["seo_score"] is None
    assert body["locales"] == ["en", "nl"]


def test_plan_returns_items(monkeypatch):
    _auth(monkeypatch)
    with patch(
        "auth_service.routers.seo.seo_repo.plan_items",
        return_value=[
            {
                "id": "i1",
                "track": "geo",
                "title": "Add stats",
                "description": "",
                "rationale": "",
                "priority": 9,
                "effort": "low",
                "action_kind": "content",
                "target": "/",
                "status": "planned",
            }
        ],
    ):
        r = client.get("/projects/acme/seo/plan")
    assert r.status_code == 200
    assert r.json()[0]["title"] == "Add stats"


def test_put_page_meta(monkeypatch):
    _auth(monkeypatch)
    with patch(
        "auth_service.routers.seo.seo_repo.upsert_page_meta",
        return_value={
            "id": "m1",
            "route": "/",
            "locale": "en",
            "title": "Home",
            "description": "",
            "canonical": None,
            "og": {},
            "json_ld": {},
            "robots": None,
            "status": "draft",
            "updated_by": "a@b.com",
            "updated_at": "2026-06-14T00:00:00+00:00",
        },
    ) as up:
        r = client.put(
            "/projects/acme/seo/meta", json={"route": "/", "locale": "en", "title": "Home"}
        )
    assert r.status_code == 200 and r.json()["id"] == "m1"
    assert up.call_args[0][2] == "a@b.com"  # updated_by = acting user email


def test_create_article(monkeypatch):
    _auth(monkeypatch)
    with patch(
        "auth_service.routers.seo.seo_repo.create_article",
        return_value={
            "id": "a1",
            "slug": "guide",
            "locale": "en",
            "title": "Guide",
            "excerpt": "",
            "body": "x",
            "json_ld": {},
            "hero_image_url": None,
            "status": "draft",
            "updated_by": "a@b.com",
            "created_at": "t",
            "updated_at": "t",
        },
    ):
        r = client.post(
            "/projects/acme/seo/articles",
            json={"slug": "guide", "locale": "en", "title": "Guide", "body": "x"},
        )
    assert r.status_code == 200 and r.json()["slug"] == "guide"


def test_delete_article(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.delete_article") as d:
        r = client.delete("/projects/acme/seo/articles/a1")
    assert r.status_code == 200 and r.json()["deleted"] is True
    d.assert_called_once()


def test_public_meta_published(monkeypatch):
    # resolve slug->id without auth
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug", lambda slug: "proj-acme")
    with patch(
        "auth_service.routers.seo.seo_repo.published_meta",
        return_value={
            "title": "Home",
            "description": "d",
            "canonical": "/",
            "og": {},
            "json_ld": {},
            "robots": None,
        },
    ):
        r = client.get("/projects/acme/seo/public/meta?route=/&locale=en")
    assert r.status_code == 200 and r.json()["title"] == "Home"


def test_public_meta_missing_returns_empty(monkeypatch):
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug", lambda slug: "proj-acme")
    with patch("auth_service.routers.seo.seo_repo.published_meta", return_value=None):
        r = client.get("/projects/acme/seo/public/meta?route=/missing&locale=en")
    assert r.status_code == 200 and r.json() == {}


def test_router_registered():
    paths = {r.path for r in app.routes}
    assert "/projects/{project_slug}/seo/overview" in paths
    assert "/projects/{project_slug}/seo/public/meta" in paths


def test_update_article_missing_returns_404(monkeypatch):
    _auth(monkeypatch)
    with patch("auth_service.routers.seo.seo_repo.update_article", return_value={}):
        r = client.put(
            "/projects/acme/seo/articles/nope",
            json={"slug": "g", "locale": "en", "title": "G", "body": "x"},
        )
    assert r.status_code == 404


def test_enqueue_job(monkeypatch):
    _auth(monkeypatch)
    with patch(
        "auth_service.routers.seo.seo_repo.enqueue_job",
        return_value={
            "id": "j1",
            "kind": "run_full",
            "status": "queued",
            "requested_at": "2026-06-14T00:00:00+00:00",
        },
    ):
        r = client.post("/projects/acme/seo/jobs", json={"kind": "run_full"})
    assert r.status_code == 200 and r.json()["id"] == "j1" and r.json()["status"] == "queued"


def test_public_meta_falls_back_to_default(monkeypatch):
    # requested locale (nl) missing a title → default-locale title shows through
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug", lambda slug: "p1")
    with patch(
        "auth_service.routers.seo.seo_repo.published_meta",
        return_value={"title": "Welkom", "description": "NL desc"},
    ):
        r = client.get("/projects/acme/seo/public/meta?route=/&locale=nl")
    assert r.status_code == 200 and r.json()["title"] == "Welkom"


def test_translate_endpoint_fills_locales(monkeypatch):
    _auth(monkeypatch)  # admin
    # SEC-061: keep the rate-limiter hermetic (no real DB) and within limit here.
    monkeypatch.setattr("auth_service.core.pg_rate_limit.allow", lambda *a, **k: True)
    calls = {}

    def fake_fill(project, kind):
        calls["kind"] = kind
        return {"translated": 2}

    monkeypatch.setattr(
        "auth_service.routers.seo._translate_seo_for_project",
        lambda project, kind: fake_fill(project, kind),
    )
    r = client.post("/projects/acme/seo/translate", json={"kind": "meta"})
    assert r.status_code == 200 and calls["kind"] == "meta"


def test_translate_endpoint_rate_limited(monkeypatch):
    """SEC-061: over the per-project bucket, the paid-DeepL fan-out is refused with 429
    BEFORE _translate_seo_for_project (and its billable DeepL calls) ever runs."""
    _auth(monkeypatch)  # admin
    monkeypatch.setattr("auth_service.core.pg_rate_limit.allow", lambda *a, **k: False)

    called = {"fill": False}

    def fake_fill(project, kind):
        called["fill"] = True
        return {"translated": 2}

    monkeypatch.setattr(
        "auth_service.routers.seo._translate_seo_for_project",
        lambda project, kind: fake_fill(project, kind),
    )
    r = client.post("/projects/acme/seo/translate", json={"kind": "meta"})
    assert r.status_code == 429
    assert called["fill"] is False  # short-circuited before any DeepL work
