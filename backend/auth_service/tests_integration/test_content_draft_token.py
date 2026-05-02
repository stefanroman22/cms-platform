import pytest

pytestmark = pytest.mark.integration


def test_draft_without_token_returns_401(client):
    r = client.get("/content/e2e-test-project/draft")
    assert r.status_code == 401


def test_draft_with_wrong_token_returns_401(client):
    r = client.get(
        "/content/e2e-test-project/draft",
        headers={"X-CMS-Preview-Token": "totally-not-the-token"},
    )
    assert r.status_code == 401


def test_draft_with_valid_token_returns_200(client, admin_client):
    detail = admin_client.get("/admin/projects/e2e-test-project")
    assert detail.status_code == 200
    preview_token = detail.json().get("preview_token")
    if not preview_token:
        pytest.skip("e2e-test-project has no preview_token set; skipping draft test")
    r = client.get(
        "/content/e2e-test-project/draft",
        headers={"X-CMS-Preview-Token": preview_token},
    )
    assert r.status_code == 200
    assert "content" in r.json()
