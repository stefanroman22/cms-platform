from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from auth_service.services.storage_gc import prune_unreferenced_uploads

OLD = (datetime.now(UTC) - timedelta(days=3)).isoformat()
NEW = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()


class FakeStore:
    def __init__(self, tree):
        self.tree = tree
        self.removed = None

    def list(self, path, _opts=None):
        return self.tree.get(path, [])

    def remove(self, paths):
        self.removed = list(paths)


def _sb(store):
    sb = MagicMock()
    sb.storage.from_.return_value = store
    return sb


def _file(name, created):
    return {"name": name, "id": f"id-{name}", "created_at": created}


def test_removes_only_old_unreferenced_files_across_service_folders():
    store = FakeStore(
        {
            "acme": [{"name": "general_logo", "id": None}, {"name": "gallery", "id": None}],
            "acme/general_logo": [_file("keep.png", OLD), _file("old.png", OLD)],
            "acme/gallery": [_file("fresh.png", NEW), _file("gone.jpg", OLD)],
        }
    )
    contents = [
        {
            "url": "https://x.supabase.co/storage/v1/object/public/cms-files/acme/general_logo/keep.png"
        }
    ]

    removed = prune_unreferenced_uploads(_sb(store), "acme", contents)

    assert sorted(removed) == ["acme/gallery/gone.jpg", "acme/general_logo/old.png"]
    assert sorted(store.removed) == sorted(removed)


def test_references_in_any_locale_or_nested_json_are_kept():
    store = FakeStore({"acme": [{"name": "hero", "id": None}], "acme/hero": [_file("a.jpg", OLD)]})
    contents = [None, {"items": [{"img": "…/cms-files/acme/hero/a.jpg"}]}]

    assert prune_unreferenced_uploads(_sb(store), "acme", contents) == []
    assert store.removed is None


def test_files_without_a_timestamp_are_never_removed():
    store = FakeStore({"acme": [_file("loose.png", None)]})

    assert prune_unreferenced_uploads(_sb(store), "acme", []) == []


def test_publish_still_succeeds_when_storage_gc_fails(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(
            data=[
                {
                    "id": "e1",
                    "project_service_id": "svc-1",
                    "locale": "en",
                    "draft_content": {"t": "new"},
                    "published_content": {"t": "old"},
                }
            ]
        ),
        MagicMock(data=[]),
        MagicMock(data=[{"last_published_at": "2026-09-27T10:00:00Z"}]),
    ]

    def boom(*_a, **_k):
        raise RuntimeError("storage down")

    monkeypatch.setattr("auth_service.routers.publish.prune_unreferenced_uploads", boom)
    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    assert res.json()["published_count"] == 1
