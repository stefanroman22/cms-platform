import time

import pytest

pytestmark = pytest.mark.integration


SERVICE_KEY = "e2e_text"
SEED = {"title": "E2E Title", "body": "E2E Body"}


@pytest.fixture
def restore_text(user_client):
    """Reset e2e_text to seed value after the test, regardless of pass/fail."""
    yield
    user_client.put(
        f"/projects/e2e-test-project/services/{SERVICE_KEY}",
        json={"content": SEED},
    )
    user_client.post("/projects/e2e-test-project/publish")


def test_publish_round_trip(client, user_client, restore_text):
    ts = int(time.time())
    new_content = {"title": f"E2E Title {ts}", "body": f"E2E Body {ts}"}

    put = user_client.put(
        f"/projects/e2e-test-project/services/{SERVICE_KEY}",
        json={"content": new_content},
    )
    assert put.status_code == 200

    pub_before = client.get("/content/e2e-test-project")
    assert pub_before.status_code == 200
    assert pub_before.json()["content"][SERVICE_KEY].get("title") != new_content["title"]

    pub = user_client.post("/projects/e2e-test-project/publish")
    assert pub.status_code == 200
    assert pub.json()["published_count"] >= 1

    pub_after = client.get("/content/e2e-test-project")
    assert pub_after.status_code == 200
    assert pub_after.json()["content"][SERVICE_KEY]["title"] == new_content["title"]
