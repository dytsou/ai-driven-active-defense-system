from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.nycu_oauth_service import AUTH_URL, nycu_login_url


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


def test_nycu_oauth_start_redirects_to_nycu(client: TestClient, oauth_settings):
    response = client.get("/api/v1/auth/oauth/nycu/start?next=/me", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://id.nycu.edu.tw/o/authorize/")
    assert "client_id=test-client-id" in location
    assert "scope=profile" in location
    assert "state=" in location


def test_nycu_oauth_callback_invalid_state(client: TestClient, oauth_settings):
    response = client.get(
        "/api/v1/auth/oauth/nycu/callback?code=abc&state=missing",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/?oauth_error=invalid_state"


def test_nycu_oauth_callback_success(client: TestClient, oauth_settings):
    state = "oauth-test-state"
    client.app.state.redis.setex(
        "oauth:nycu:state:oauth-test-state",
        600,
        '{"next": "/me", "username": "112345678"}',
    )

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "access-token"}

    profile_response = MagicMock()
    profile_response.status_code = 200
    profile_response.json.return_value = {
        "username": "112345678",
        "email": "112345678@nycu.edu.tw",
    }

    with patch("app.services.nycu_oauth_service.httpx.post", return_value=token_response), patch(
        "app.services.nycu_oauth_service.httpx.get", return_value=profile_response
    ):
        response = client.get(
            "/api/v1/auth/oauth/nycu/callback?code=valid-code&state=oauth-test-state",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/me"
    assert response.cookies.get("session_id")

    me = client.get("/api/v1/auth/me", cookies={"session_id": response.cookies.get("session_id")})
    assert me.status_code == 200
    assert me.json()["username"] == "112345678"
    assert me.json()["email"] == "112345678@nycu.edu.tw"


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


def test_login_nycu_user_returns_success(auth_client: TestClient, seeded_db, oauth_settings):
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "access-token"}

    profile_response = MagicMock()
    profile_response.status_code = 200
    profile_response.json.return_value = {
        "username": "111550073",
        "email": "111550073@nycu.edu.tw",
    }

    with patch(
        "app.api.routes.auth.collect_authorization_code",
        return_value="oauth-code-from-http",
    ), patch("app.services.nycu_oauth_service.httpx.post", return_value=token_response), patch(
        "app.services.nycu_oauth_service.httpx.get", return_value=profile_response
    ):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={
                "username": "111550073",
                "password": "PortalPass123!",
                "keystroke": {"present": True},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert response.cookies.get("session_id")
