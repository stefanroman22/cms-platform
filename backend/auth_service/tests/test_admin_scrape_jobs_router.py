from unittest.mock import MagicMock


def test_list_jobs_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.get("/admin/scrape-jobs").status_code == 403


def test_create_job_validates_params(client, auth_as, admin_user):
    auth_as(admin_user)
    bad = client.post("/admin/scrape-jobs", json={"params": {"country": "NL"}})
    assert bad.status_code == 422  # category missing


def test_create_job_happy_path(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "job-1",
                "status": "pending",
                "triggered_by": "cms",
                "created_at": "2026-05-17T10:00:00Z",
                "params": {"category": "restaurants", "country": "NL"},
            }
        ]
    )
    resp = client.post(
        "/admin/scrape-jobs",
        json={"params": {"category": "restaurants", "country": "NL"}},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_cancel_pending_job(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "job-1",
                "status": "pending",
                "triggered_by": "cms",
                "created_at": "x",
                "params": {"category": "x", "country": "NL"},
            }
        ),
        MagicMock(
            data=[
                {
                    "id": "job-1",
                    "status": "cancelled",
                    "triggered_by": "cms",
                    "created_at": "x",
                    "params": {"category": "x", "country": "NL"},
                }
            ]
        ),
    ]
    resp = client.patch("/admin/scrape-jobs/job-1", json={"status": "cancelled"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
