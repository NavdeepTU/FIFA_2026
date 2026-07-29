def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_id_header_present(client):
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers
