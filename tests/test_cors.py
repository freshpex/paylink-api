def test_browser_preflight_and_unauthenticated_response(client):
    origin = "http://localhost:5173"
    response = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["Access-Control-Allow-Origin"] == origin


def test_untrusted_browser_preflight_is_rejected(client):
    response = client.options(
        "/api/v1/auth/register",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 400
    assert "Access-Control-Allow-Origin" not in response.headers
