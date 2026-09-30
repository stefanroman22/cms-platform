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
    monkeypatch.setattr("auth_service.routers.workspace.get_provider", lambda: _BarrierProvider(3))
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
    assert res.json()[0]["last_updated"] == "2026-09-30T10:00:00Z"
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
