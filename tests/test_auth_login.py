from fastapi.testclient import TestClient
import secrets

from app.core.config import settings


NORMAL_KEYSTROKE = {
    "keystroke": {
        "present": True,
        "timing": {
            "dwell_times": [95, 92, 98],
            "flight_times": [110, 108, 112],
        },
    }
}


def _login(client: TestClient, username: str, password: str, **extra):
    payload = {"username": username, "password": password, **extra}
    return client.post("/api/v1/auth/login", json=payload)


def test_valid_login_returns_success(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "demo1", settings.seed_demo1_password, **NORMAL_KEYSTROKE)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_invalid_password_returns_invalid_credentials(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "demo1", "wrong-password")
    assert response.status_code == 401
    assert response.json()["status"] == "invalid_credentials"


def test_unknown_user_returns_invalid_credentials(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "nobody", "Demo123!")
    assert response.status_code == 401
    assert response.json()["status"] == "invalid_credentials"


def test_login_sets_session_cookie(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "demo1", settings.seed_demo1_password, **NORMAL_KEYSTROKE)
    assert response.status_code == 200
    assert "session_id" in response.cookies


def test_session_allows_authenticated_request(auth_client: TestClient, seeded_db):
    login = _login(auth_client, "demo1", settings.seed_demo1_password, **NORMAL_KEYSTROKE)
    session_id = login.cookies.get("session_id")
    response = auth_client.get("/api/v1/auth/me", cookies={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["username"] == "demo1"


def test_blocked_ip_returns_blocked(auth_client: TestClient, seeded_db, fake_redis, monkeypatch):
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


def test_rate_limit_returns_too_many_requests(auth_client: TestClient, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_login_per_min", 2)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "198.51.100.10"}

    for _ in range(2):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "demo1", "password": "wrong"},
            headers=headers,
        )
        assert response.status_code in (401, 403)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": settings.seed_demo1_password},
        headers=headers,
    )
    assert response.status_code == 429
    assert response.json()["status"] == "rate_limited"


def test_missing_keystroke_requires_mfa(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "demo1", settings.seed_demo1_password)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mfa_required"
    assert body["mfa_required"] is True


def test_gateway_adds_attempt_id_header(auth_client: TestClient, seeded_db):
    response = _login(auth_client, "demo1", settings.seed_demo1_password, **NORMAL_KEYSTROKE)
    assert response.headers.get("X-Attempt-Id")


def test_nine_digit_username_requires_mfa_without_keystroke(
    auth_client: TestClient, seeded_db, monkeypatch
):
    from app.core.security import hash_password
    from app.db.models import RegistrationStatus, User, UserRole

    user = User(
        username="112345678",
        email="112345678@nycu.edu.tw",
        password_hash=hash_password("StudentPass1"),
        role=UserRole.USER.value,
        registration_status=RegistrationStatus.COMPLETE.value,
        nycu_oauth_subject="112345678",
    )
    seeded_db.add(user)
    seeded_db.commit()

    response = _login(auth_client, "112345678", "StudentPass1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mfa_required"
    assert body["mfa_required"] is True


def test_nine_digit_username_not_auto_provisioned(auth_client: TestClient, seeded_db):
    login = _login(auth_client, "998877665", "StudentPass1", **NORMAL_KEYSTROKE)
    assert login.status_code == 403
    assert login.json()["status"] == "registration_required"


def test_nine_digit_registered_user_accepts_any_password(
    auth_client: TestClient, seeded_db
):
    from app.core.security import hash_password
    from app.db.models import RegistrationStatus, User, UserRole

    user = User(
        username="556677889",
        email="556677889@nycu.edu.tw",
        password_hash=hash_password(secrets.token_urlsafe(16)),
        role=UserRole.USER.value,
        registration_status=RegistrationStatus.COMPLETE.value,
        nycu_oauth_subject="556677889",
    )
    seeded_db.add(user)
    seeded_db.commit()

    retry = _login(auth_client, "556677889", "WrongPass1", **NORMAL_KEYSTROKE)
    assert retry.status_code == 200
    assert retry.json()["status"] == "success"


def test_nycu_registered_user_missing_keystroke_requires_mfa(
    auth_client: TestClient, seeded_db
):
    from app.core.security import hash_password
    from app.db.models import RegistrationStatus, User, UserRole

    user = User(
        username="223344556",
        email="223344556@nycu.edu.tw",
        password_hash=hash_password("unused"),
        role=UserRole.USER.value,
        registration_status=RegistrationStatus.COMPLETE.value,
        nycu_oauth_subject="223344556",
    )
    seeded_db.add(user)
    seeded_db.commit()

    response = _login(auth_client, "223344556", "any-password")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mfa_required"
    assert body["mfa_required"] is True
    assert body["challenge_id"]
