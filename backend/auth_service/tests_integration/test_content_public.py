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


@pytest.mark.xfail(
    strict=False,
    reason=(
        ".maybe_single() fix in routers/content.py:_resolve_project landed on dev "
        "(commit dc3dbff). Production backend at cms-backend-roman.vercel.app "
        "still serves master, where _resolve_project uses .single() and PGRST116 "
        "leaks as 500. Remove this xfail after master fast-forwards to dev and "
        "Vercel redeploys."
    ),
)
def test_public_content_returns_404_for_unknown_slug(client):
    r = client.get("/content/this-slug-does-not-exist-9999")
    assert r.status_code == 404


def test_content_types_returns_typescript_dts(client):
    """The /types endpoint emits an auto-generated TypeScript .d.ts string,
    not a JSON service-type listing. Verify the shape and that all seeded
    service keys are referenced."""
    r = client.get("/content/e2e-test-project/types")
    assert r.status_code == 200
    body = r.text
    assert "export interface CMSContent" in body
    assert 'project_slug: "e2e-test-project"' in body
    assert "e2e_text" in body
    assert "e2e_features" in body
