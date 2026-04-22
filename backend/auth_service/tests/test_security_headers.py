def test_security_headers_emitted_on_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"


def test_security_headers_emitted_on_404(client):
    res = client.get("/this/endpoint/does/not/exist")
    assert res.status_code == 404
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"
