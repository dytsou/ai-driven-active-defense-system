import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def _login(client: TestClient, username: str, password: str, **extra):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, **extra},
    )


def test_xff_ignored_when_trust_proxy_disabled(auth_client: TestClient, seeded_db, fake_redis):
    from app.services.blocklist_manager import BlocklistManager

    BlocklistManager(fake_redis).block_ip("203.0.113.50", ttl=60)
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert response.status_code == 200


def test_xff_honored_when_trust_proxy_enabled(
    auth_client: TestClient, seeded_db, fake_redis, monkeypatch
):
    from app.services.blocklist_manager import BlocklistManager

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    BlocklistManager(fake_redis).block_ip("203.0.113.50", ttl=60)
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert response.status_code == 403
    assert response.json()["status"] == "blocked"


def test_password_spray_triggers_block(
    auth_client: TestClient, seeded_db, monkeypatch
):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "203.0.113.99"}
    usernames = ["demo1", "demo2", "admin", "nobody", "guest", "root", "alice", "bob"]

    saw_invalid = False
    for username in usernames:
        response = _login(auth_client, username, "wrong-password", headers=headers)
        assert response.status_code in (401, 403)
        if response.status_code == 401:
            saw_invalid = True

    assert saw_invalid
    response = _login(auth_client, "demo1", settings.seed_demo1_password, headers=headers)
    assert response.status_code == 403
    assert response.json()["status"] == "blocked"


def test_mfa_send_rate_limited(auth_client: TestClient, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_mfa_send_per_min", 1)
    login = _login(auth_client, "demo1", settings.seed_demo1_password)
    challenge_id = login.json()["challenge_id"]

    first = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert first.status_code == 200

    second = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert second.status_code == 429
    assert second.json()["status"] == "rate_limited"


def test_mfa_send_blocked_ip(auth_client: TestClient, seeded_db, fake_redis, monkeypatch):
    from app.services.blocklist_manager import BlocklistManager

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "198.51.100.20"}
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers=headers,
    )
    challenge_id = login.json()["challenge_id"]
    BlocklistManager(fake_redis).block_ip("198.51.100.20", ttl=60)
    response = auth_client.post(
        "/api/v1/auth/mfa/send",
        json={"challenge_id": challenge_id},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["status"] == "blocked"


def test_login_audit_includes_latency(auth_client: TestClient, seeded_db):
    keystroke = {
        "keystroke": {
            "present": True,
            "timing": {
                "dwell_times": [95, 92, 98],
                "flight_times": [110, 108, 112],
            },
        }
    }
    _login(
        auth_client,
        "demo1",
        settings.seed_demo1_password,
        **keystroke,
    )
    admin_login = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": settings.seed_admin_password,
            **keystroke,
        },
    )
    session_id = admin_login.cookies.get("session_id")
    events = auth_client.get("/admin/api/events", cookies={"session_id": session_id})
    assert events.status_code == 200
    login_events = [e for e in events.json()["events"] if e["event_type"] == "login_success"]
    assert login_events
    assert "latency_ms" in login_events[0]["payload"]
