import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def _login(client: TestClient, username: str, password: str, **extra):
    payload = {"username": username, "password": password, **extra}
    return client.post("/api/v1/auth/login", json=payload)


def test_valid_login_returns_success(client: TestClient, seeded_db):
    response = _login(client, "demo1", settings.seed_demo1_password)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"


def test_invalid_password_returns_invalid_credentials(client: TestClient, seeded_db):
    response = _login(client, "demo1", "wrong-password")
    assert response.status_code == 401
    assert response.json()["status"] == "invalid_credentials"


def test_unknown_user_returns_invalid_credentials(client: TestClient, seeded_db):
    response = _login(client, "nobody", "Demo123!")
    assert response.status_code == 401
    assert response.json()["status"] == "invalid_credentials"


def test_login_sets_session_cookie(client: TestClient, seeded_db):
    response = _login(client, "demo1", settings.seed_demo1_password)
    assert response.status_code == 200
    assert "session_id" in response.cookies


def test_session_allows_authenticated_request(client: TestClient, seeded_db):
    login = _login(client, "demo1", settings.seed_demo1_password)
    session_id = login.cookies.get("session_id")
    response = client.get("/api/v1/auth/me", cookies={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["username"] == "demo1"


def test_blocked_ip_returns_blocked(client: TestClient, seeded_db, fake_redis):
    from app.services.blocklist_manager import BlocklistManager

    BlocklistManager(fake_redis).block_ip("203.0.113.50", ttl=60)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert response.status_code == 403
    assert response.json()["status"] == "blocked"


def test_rate_limit_returns_too_many_requests(client: TestClient, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_login_per_min", 2)
    headers = {"X-Forwarded-For": "198.51.100.10"}

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "demo1", "password": "wrong"},
            headers=headers,
        )
        assert response.status_code in (401, 403)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers=headers,
    )
    assert response.status_code == 429
    assert response.json()["status"] == "rate_limited"


def test_gateway_adds_attempt_id_header(client: TestClient, seeded_db):
    response = _login(client, "demo1", settings.seed_demo1_password)
    assert response.headers.get("X-Attempt-Id")
