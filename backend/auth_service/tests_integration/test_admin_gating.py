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
    r = admin_client.get("/admin/projects")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "e2e-test-project" in slugs


def test_admin_can_list_clients(admin_client):
    r = admin_client.get("/admin/clients")
    assert r.status_code == 200
    emails = [c["email"] for c in r.json()]
    assert "e2e-user@cms-test.dev" in emails
    assert "e2e-admin@cms-test.dev" in emails
