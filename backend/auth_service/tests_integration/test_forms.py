import pytest

pytestmark = pytest.mark.integration


def test_form_submit_returns_200(client):
    r = client.post(
        "/forms/e2e-test-project/e2e_contact_form",
        json={
            "name": "E2E test",
            "email": "e2e-user@cms-test.dev",
            "message": "[E2E-TEST] integration test submission",
        },
        headers={"Origin": "https://cms-frontend-roman.vercel.app"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True


def test_form_submit_404_for_missing_form_key(client):
    r = client.post(
        "/forms/e2e-test-project/no_such_form",
        json={"message": "x"},
        headers={"Origin": "https://cms-frontend-roman.vercel.app"},
    )
    assert r.status_code == 404


def test_form_submit_422_on_empty_body(client):
    r = client.post(
        "/forms/e2e-test-project/e2e_contact_form",
        json={},
        headers={"Origin": "https://cms-frontend-roman.vercel.app"},
    )
    assert r.status_code == 422
