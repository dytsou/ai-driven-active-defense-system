import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import RegistrationStatus, User, UserRole
from app.services.registration_service import (
    REG_BINDING_COOKIE,
    REG_LINE_STATE_PREFIX,
    REG_NYCU_STATE_PREFIX,
    RegistrationService,
)


@pytest.fixture()
def reg_service(seeded_db, fake_redis):
    return RegistrationService(db=seeded_db, redis_client=fake_redis)


def test_registration_start_returns_token(reg_service, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")
    bundle = reg_service.start()
    assert bundle.response.status == "started"
    assert bundle.response.registration_token
    assert bundle.response.nycu_authorization_url
    assert bundle.binding


def test_nycu_callback_creates_pending_line_user(reg_service, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")

    bundle = reg_service.start()
    token = bundle.response.registration_token
    state = "test-state"
    fake_redis.setex(
        f"{REG_NYCU_STATE_PREFIX}{state}",
        900,
        json.dumps({"registration_token": token}),
    )

    class FakeOAuth:
        def exchange_code(self, code):
            return "access"

        def fetch_profile(self, access_token):
            from app.services.nycu_oauth_service import NycuOAuthProfile

            return NycuOAuthProfile(username="112345678", email="112345678@nycu.edu.tw")

    monkeypatch.setattr(reg_service, "_nycu_service", lambda: FakeOAuth())

    result = reg_service.handle_nycu_callback("code", state, bundle.binding)
    user = seeded_db.query(User).filter(User.username == "112345678").one()
    assert user.registration_status == RegistrationStatus.PENDING_LINE.value
    assert user.nycu_oauth_subject == "112345678"
    assert result.registration_token == token


def test_nycu_callback_rejects_missing_binding(reg_service, monkeypatch, fake_redis):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")

    bundle = reg_service.start()
    token = bundle.response.registration_token
    state = "test-state"
    fake_redis.setex(
        f"{REG_NYCU_STATE_PREFIX}{state}",
        900,
        json.dumps({"registration_token": token}),
    )

    with pytest.raises(Exception) as exc:
        reg_service.handle_nycu_callback("code", state, None)
    assert exc.value.code == "invalid_state"


def test_line_callback_binds_user(reg_service, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")
    monkeypatch.setattr(settings, "line_login_channel_id", "line-id")
    monkeypatch.setattr(settings, "line_login_channel_secret", "line-secret")
    monkeypatch.setattr(settings, "line_login_callback_url", "http://localhost/callback")

    user = User(
        username="112345679",
        email="112345679@nycu.edu.tw",
        password_hash=hash_password("unused"),
        role=UserRole.USER.value,
        registration_status=RegistrationStatus.PENDING_LINE.value,
        nycu_oauth_subject="112345679",
    )
    seeded_db.add(user)
    seeded_db.commit()

    token = "reg-token"
    binding = "binding-secret"
    reg_service._save_session(
        token,
        {
            "step": "pending_line",
            "user_id": str(user.id),
            "binding": binding,
            "username": user.username,
            "email": user.email,
        },
    )

    state = "line-state"
    fake_redis.setex(
        f"{REG_LINE_STATE_PREFIX}{state}",
        900,
        json.dumps({"registration_token": token, "nonce": "nonce-value"}),
    )

    class FakeLine:
        def exchange_code(self, code):
            return "id-token"

        def verify_id_token(self, id_token, nonce=None):
            return "line-user-1"

    monkeypatch.setattr(reg_service, "_line_service", lambda: FakeLine())

    result = reg_service.handle_line_callback("code", state, binding)
    seeded_db.refresh(user)
    assert user.line_user_id == "line-user-1"
    assert result.line_user_id == "line-user-1"


def test_unregistered_nine_digit_login_rejected(auth_client: TestClient, seeded_db):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "112345678", "password": "StudentPass1"},
    )
    assert response.status_code == 401
    assert response.json()["status"] == "invalid_credentials"


def test_register_start_sets_binding_cookie(auth_client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")
    response = auth_client.post("/api/v1/auth/register/start")
    assert response.status_code == 200
    assert REG_BINDING_COOKIE in response.cookies
