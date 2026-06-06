from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import RegistrationStatus, User, UserRole
from app.services.nycu_oauth_service import nycu_login_url

NORMAL_KEYSTROKE = {
    "keystroke": {
        "present": True,
        "timing": {
            "dwell_times": [95, 92, 98],
            "flight_times": [110, 108, 112],
        },
    }
}


@pytest.fixture()
def oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-client-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "base_url", "http://testserver")


def test_nycu_login_url_wraps_authorize_url():
    auth_url = (
        "https://id.nycu.edu.tw/o/authorize/?client_id=test&response_type=code&state=abc"
    )
    login_url = nycu_login_url(auth_url)
    assert login_url.startswith("https://id.nycu.edu.tw/accounts/login/?next=")
    parsed = urlparse(login_url)
    next_url = parse_qs(parsed.query)["next"][0]
    assert next_url == auth_url


def test_nycu_oauth_start_requires_configuration(client: TestClient):
    response = client.get("/api/v1/auth/oauth/nycu/start", follow_redirects=False)
    assert response.status_code == 503


def test_nycu_oauth_start_redirects_to_register(client: TestClient, oauth_settings):
    response = client.get("/api/v1/auth/oauth/nycu/start?next=/me", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/register"


def test_nycu_oauth_callback_redirects_to_register(client: TestClient, oauth_settings):
    response = client.get(
        "/api/v1/auth/oauth/nycu/callback?code=abc&state=missing",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/register?error=use_registration_flow"


def test_login_demo_user_stays_local_when_oauth_enabled(auth_client: TestClient, seeded_db, oauth_settings):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo1",
            "password": "Demo123!",
            "keystroke": {"present": True},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"success", "mfa_required"}


def test_login_nycu_user_requires_registration(auth_client: TestClient, seeded_db, oauth_settings):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "111550073",
            "password": "PortalPass123!",
            "keystroke": {"present": True},
        },
    )

    assert response.status_code == 403
    assert response.json()["status"] == "registration_required"


def test_login_nycu_registered_user_returns_success(auth_client: TestClient, seeded_db, oauth_settings):
    user = User(
        username="111550073",
        email="111550073@nycu.edu.tw",
        password_hash=hash_password("unused"),
        role=UserRole.USER.value,
        registration_status=RegistrationStatus.COMPLETE.value,
        nycu_oauth_subject="111550073",
    )
    seeded_db.add(user)
    seeded_db.commit()

    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "111550073",
            "password": "PortalPass123!",
            **NORMAL_KEYSTROKE,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert response.cookies.get("session_id")
