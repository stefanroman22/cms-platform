import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/admin/projects"),
        ("GET", "/admin/clients"),
        ("GET", "/admin/projects/e2e-test-project"),
        ("PATCH", "/admin/projects/e2e-test-project"),
    ],
)
def test_admin_endpoint_403_for_regular_user(method, path, user_client):
    r = user_client.request(method, path, json={} if method == "PATCH" else None)
    assert r.status_code == 403, f"{method} {path} → {r.status_code} {r.text}"


def test_admin_can_list_projects(admin_client):
    # `?include_test=true` because the seed fixture `e2e-test-project`
    # matches `is_test_slug` (`e2e-test-project` literal) and the
    # filter introduced in services/test_data.py hides it from the
    # default response.
    r = admin_client.get("/admin/projects?include_test=true")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "e2e-test-project" in slugs


def test_admin_can_list_clients(admin_client):
    # Same reason as above — the seed e2e-* @cms-test.dev users match
    # `is_test_email`.
    r = admin_client.get("/admin/clients?include_test=true")
    assert r.status_code == 200
    emails = [c["email"] for c in r.json()]
    assert "e2e-user@cms-test.dev" in emails
    assert "e2e-admin@cms-test.dev" in emails
