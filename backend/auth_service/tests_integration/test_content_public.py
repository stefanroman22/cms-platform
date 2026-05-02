import pytest

pytestmark = pytest.mark.integration


def test_public_content_returns_200(client):
    r = client.get("/content/e2e-test-project")
    assert r.status_code == 200
    data = r.json()
    assert "content" in data
    assert "e2e_text" in data["content"]
    assert "e2e_features" in data["content"]
    assert "e2e_contact_form" not in data["content"]


def test_public_content_returns_404_for_unknown_slug(client):
    r = client.get("/content/this-slug-does-not-exist-9999")
    assert r.status_code == 404


def test_content_types_returns_8_types(client):
    r = client.get("/content/e2e-test-project/types")
    assert r.status_code == 200
    slugs = {t["slug"] for t in r.json()}
    assert {
        "text_block",
        "image",
        "gallery",
        "video",
        "file_download",
        "key_value",
        "email_config",
        "repeater",
    } <= slugs
