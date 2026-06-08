from unittest.mock import MagicMock


def test_list_jobs_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.get("/admin/scrape-jobs").status_code == 403


def test_create_job_validates_params(client, auth_as, admin_user):
    auth_as(admin_user)
    bad = client.post("/admin/scrape-jobs", json={"params": {"lead_type": "bogus"}})
    assert bad.status_code == 422  # lead_type not in Literal allowlist


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


def test_create_job_with_empty_params_uses_defaults(mock_supabase, client, auth_as, admin_user):
    """An empty params body must succeed — every field is optional with a default."""
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "job-defaults",
                "created_at": "2026-05-20T10:00:00Z",
                "status": "pending",
                "params": {
                    "category": "businesses",
                    "country": "NL",
                    "cities": [],
                    "areas": [],
                    "max_results_per_area": 20,
                    "language": "en",
                    "lead_type": "website",
                    "with_reviews": True,
                    "review_limit": 10,
                    "filters": {
                        "min_rating": None,
                        "max_rating": None,
                        "min_reviews": 5,
                        "max_reviews": None,
                        "web_presence": ["none", "social_only"],
                    },
                },
                "started_at": None,
                "finished_at": None,
                "results_found": None,
                "results_inserted": None,
                "results_skipped": None,
                "error": None,
                "triggered_by": "cms",
            }
        ]
    )
    resp = client.post("/admin/scrape-jobs", json={"params": {}})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["params"]["category"] == "businesses"
    assert body["params"]["country"] == "NL"
    assert body["params"]["with_reviews"] is True
    assert body["params"]["filters"]["web_presence"] == ["none", "social_only"]
    assert body["params"]["filters"]["min_reviews"] == 5
