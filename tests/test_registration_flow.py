import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import RegistrationStatus, User, UserRole
from app.services.registration_service import (
    REG_LINE_STATE_PREFIX,
    REG_NYCU_STATE_PREFIX,
    REG_SESSION_PREFIX,
    RegistrationService,
)


@pytest.fixture()
def reg_service(seeded_db, fake_redis):
    return RegistrationService(db=seeded_db, redis_client=fake_redis)


def test_registration_start_returns_token(reg_service, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")
    result = reg_service.start()
    assert result.status == "started"
    assert result.registration_token
    assert result.nycu_authorization_url


def test_nycu_callback_creates_pending_line_user(reg_service, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "nycu_oauth_client_id", "test-id")
    monkeypatch.setattr(settings, "nycu_oauth_client_secret", "test-secret")

    start = reg_service.start()
    token = start.registration_token
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

    result = reg_service.handle_nycu_callback("code", state)
    user = seeded_db.query(User).filter(User.username == "112345678").one()
    assert user.registration_status == RegistrationStatus.PENDING_LINE.value
    assert user.nycu_oauth_subject == "112345678"
    assert result.registration_token == token


def test_unregistered_nine_digit_login_rejected(auth_client: TestClient, seeded_db):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "112345678", "password": "StudentPass1"},
    )
    assert response.status_code == 403
    assert response.json()["status"] == "registration_required"
