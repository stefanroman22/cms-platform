"""Integration tests for routers/issues.py — Slack notification wiring."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_create_issue_fires_slack_created(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)

    # Stub Supabase insert to return one row.
    inserted_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "created_at": "2026-05-15T10:00:00Z",
        "created_by": client_user.id,
    }
    mock_supabase.execute.return_value = MagicMock(data=[inserted_row])

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: calls.append(kw),
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "Hero broken", "description": "stretches", "priority": "High"},
    )
    assert resp.status_code == 201, resp.text

    assert len(calls) == 1
    call = calls[0]
    assert call["user_email"] == client_user.email
    assert call["issue"]["id"] == "issue-1"
    assert call["issue"]["title"] == "Hero broken"
    assert call["project"]["slug"] == "acme"
    assert call["project"]["repo_branch"] == "cms-preview"


def test_create_issue_slack_failure_does_not_break_201(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """If slack_notify raises, the API still returns 201."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-2",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )

    def boom(**kw):
        raise RuntimeError("slack down")

    monkeypatch.setattr("auth_service.routers.issues.slack_notify.notify_issue_created", boom)

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    # The service itself swallows; if a router-level guard is missing, this test
    # forces it to be added.
    assert resp.status_code == 201, resp.text


def test_create_issue_fires_solver_dispatch(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-dispatch-1",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )
    # Don't make a real dispatch HTTP call.
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: None,
    )
    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.solver_dispatch.dispatch_solver_tick",
        lambda **kw: calls.append(kw),
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201, resp.text
    assert calls == [{"issue_id": "issue-dispatch-1"}]


def test_create_issue_dispatch_failure_does_not_break_201(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """Dispatch failure must degrade silently — cron picks the issue up."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-dispatch-2",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: None,
    )

    def boom(**kw):
        raise RuntimeError("github down")

    monkeypatch.setattr("auth_service.routers.issues.solver_dispatch.dispatch_solver_tick", boom)

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201, resp.text


def test_status_pending_to_done_fires_resolved(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)

    # First SELECT returns the existing row (status=pending).
    # Then UPDATE returns the new row (status=done).
    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "done",
        "created_by": "client-uuid",
        "created_at": "2026-05-15T10:00:00Z",
    }

    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),  # pre-update SELECT (maybe_single)
        MagicMock(data=[updated_row]),  # UPDATE
        MagicMock(data={"email": "client@acme.com"}),  # email lookup
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status",
        json={"status": "done"},
    )
    assert resp.status_code == 200, resp.text

    assert len(calls) == 1
    assert calls[0]["resolver_email"] == admin_user.email
    assert calls[0]["issue"]["id"] == "issue-1"
    assert calls[0]["project"]["preview_url"] == "https://acme-dev.vercel.app"


def test_status_done_to_done_does_not_fire(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    done_row = {"id": "issue-1", "project_id": "project-acme", "status": "done"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "done",
        "created_by": None,
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=done_row),
        MagicMock(data=[updated_row]),
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch("/projects/acme/issues/issue-1/status", json={"status": "done"})
    assert resp.status_code == 200, resp.text
    assert calls == []


def test_status_pending_to_in_progress_does_not_fire(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)
    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "in_progress",
        "created_by": None,
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),
        MagicMock(data=[updated_row]),
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch("/projects/acme/issues/issue-1/status", json={"status": "in_progress"})
    assert resp.status_code == 200, resp.text
    assert calls == []


def test_status_done_persists_slack_ts(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)

    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "done",
        "created_by": "client-uuid",
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),  # pre-update SELECT
        MagicMock(data=[updated_row]),  # UPDATE status
        MagicMock(data={"email": "client@acme.com"}),  # email lookup
        MagicMock(data=[updated_row]),  # UPDATE slack_resolved_ts
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: "1715789123.001234",
    )

    resp = client.patch("/projects/acme/issues/issue-1/status", json={"status": "done"})
    assert resp.status_code == 200

    # Verify some UPDATE call set slack_resolved_ts
    update_calls = [c.args[0] for c in mock_supabase.update.call_args_list if c.args]
    ts_updates = [u for u in update_calls if "slack_resolved_ts" in u]
    assert len(ts_updates) == 1
    assert ts_updates[0]["slack_resolved_ts"] == "1715789123.001234"


def test_status_done_no_ts_when_slack_disabled(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """If slack_notify returns None, do NOT update slack_resolved_ts."""
    auth_as(admin_user)
    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "done",
        "created_by": None,
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),
        MagicMock(data=[updated_row]),
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: None,
    )

    resp = client.patch("/projects/acme/issues/issue-1/status", json={"status": "done"})
    assert resp.status_code == 200

    update_calls = [c.args[0] for c in mock_supabase.update.call_args_list if c.args]
    assert not any("slack_resolved_ts" in u for u in update_calls)


def test_admin_status_update_requires_bearer(mock_supabase, client):
    """Without Authorization header, admin endpoint returns 401."""
    resp = client.patch("/admin/issues/issue-1/status", json={"status": "done"})
    assert resp.status_code == 401


def test_admin_status_update_fires_slack_resolved(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)

    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "done",
        "created_by": "client-uuid",
        "created_at": "2026-05-16T10:00:00Z",
    }
    project_row = {
        "id": "project-acme",
        "name": "Acme",
        "slug": "acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "preview_url": "https://acme-dev.vercel.app",
        "production_url": "https://acme.vercel.app",
        "production_branch": "master",
        "user_id": "client-uuid",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),  # pre-update SELECT
        MagicMock(data=[updated_row]),  # UPDATE status
        MagicMock(data=project_row),  # project lookup
        MagicMock(data={"email": "client@acme.com"}),  # email lookup in _build_issue_out
        MagicMock(data=[updated_row]),  # UPDATE slack_resolved_ts
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: "1715789999.000001",
    )

    resp = client.patch(
        "/admin/issues/issue-1/status",
        json={"status": "done"},
        headers={"Authorization": "Bearer cmsk_dummy"},
    )
    assert resp.status_code == 200, resp.text

    update_calls = [c.args[0] for c in mock_supabase.update.call_args_list if c.args]
    ts_updates = [u for u in update_calls if "slack_resolved_ts" in u]
    assert len(ts_updates) == 1
    assert ts_updates[0]["slack_resolved_ts"] == "1715789999.000001"


def test_create_issue_persists_slack_created_ts(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """When notify_issue_created returns a ts, it is persisted as slack_created_ts."""
    auth_as(client_user)

    inserted_row = {
        "id": "issue-77",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "created_at": "2026-05-15T10:00:00Z",
        "created_by": client_user.id,
    }
    # First call (insert) returns the row; subsequent UPDATE returns it too.
    mock_supabase.execute.return_value = MagicMock(data=[inserted_row])

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: "1715865123.456789",
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201, resp.text

    # Find the UPDATE call that set slack_created_ts.
    update_calls = [
        c for c in mock_supabase.update.call_args_list if c.args and "slack_created_ts" in c.args[0]
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args[0]["slack_created_ts"] == "1715865123.456789"


def test_create_issue_no_ts_when_slack_returns_none(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """When notify_issue_created returns None (disabled/error), no UPDATE is made."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-78",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: None,
    )
    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201
    update_calls = [
        c for c in mock_supabase.update.call_args_list if c.args and "slack_created_ts" in c.args[0]
    ]
    assert len(update_calls) == 0


def test_admin_status_update_skips_when_already_done(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """No re-fire when old_status was already 'done'."""
    auth_as(admin_user)

    done_row = {"id": "issue-1", "project_id": "project-acme", "status": "done"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "done",
        "created_by": None,
        "created_at": "2026-05-16T10:00:00Z",
    }
    project_row = {
        "id": "project-acme",
        "name": "Acme",
        "slug": "acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "production_branch": "master",
        "preview_url": "https://acme-dev.vercel.app",
        "production_url": "https://acme.vercel.app",
        "user_id": "client-uuid",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=done_row),
        MagicMock(data=[updated_row]),
        MagicMock(data=project_row),
    ]

    calls = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw) or None,
    )

    resp = client.patch(
        "/admin/issues/issue-1/status",
        json={"status": "done"},
        headers={"Authorization": "Bearer cmsk_dummy"},
    )
    assert resp.status_code == 200, resp.text
    assert calls == []
