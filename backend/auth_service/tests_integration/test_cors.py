import pytest

pytestmark = pytest.mark.integration


def test_preflight_from_vercel_origin_succeeds(client):
    """Production CORS regex accepts any *.vercel.app origin."""
    r = client.options(
        "/auth/login",
        headers={
            "Origin": "https://it-global-services.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert r.status_code in (200, 204), r.text
    assert r.headers.get("access-control-allow-origin") == "https://it-global-services.vercel.app"
    assert "POST" in r.headers.get("access-control-allow-methods", "")


def test_preflight_from_unknown_origin_rejected(client):
    r = client.options(
        "/auth/login",
        headers={
            "Origin": "https://attacker.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.headers.get("access-control-allow-origin") != "https://attacker.example.com"
