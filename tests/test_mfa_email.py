import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.services.email_delivery import EmailDeliveryService


def _patch_email_send(monkeypatch):
    monkeypatch.setattr(
        EmailDeliveryService,
        "send_login_code",
        lambda self, _to, _otp: True,
    )


def _login(auth_client: TestClient, **extra):
    payload = {"username": "demo1", "password": settings.seed_demo1_password, **extra}
    return auth_client.post("/api/v1/auth/login", json=payload)


def test_mfa_flow_issues_and_verifies_otp(
    auth_client: TestClient, seeded_db, fake_redis, monkeypatch
):
    _patch_email_send(monkeypatch)
    login = _login(auth_client)
    assert login.json()["status"] == "mfa_required"
    challenge_id = login.json()["challenge_id"]

    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.status_code == 200
    body = send.json()
    assert body["status"] == "sent"
    assert body["delivery_target"] == "d***1@active-defense.local"

    stored = fake_redis.get(f"mfa:otp:{challenge_id}")
    assert stored is not None
    otp = stored.split(":")[0]

    verify = auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "otp": otp},
    )
    assert verify.status_code == 200
    assert verify.json()["status"] == "success"
    assert "session_id" in verify.cookies


def test_mfa_locks_after_three_wrong_otps(
    auth_client: TestClient, seeded_db, fake_redis, monkeypatch
):
    _patch_email_send(monkeypatch)
    login = _login(auth_client)
    challenge_id = login.json()["challenge_id"]
    auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})

    for i in range(3):
        response = auth_client.post(
            "/api/v1/auth/mfa/verify",
            json={"challenge_id": challenge_id, "otp": "000000"},
        )
        if i == 2:
            assert response.json()["status"] == "challenge_locked"
            return

    pytest.fail("expected challenge to lock on third invalid OTP")


def test_mfa_send_uses_nycu_oauth_synced_email(
    auth_client: TestClient,
    seeded_db,
    db_session,
    fake_redis,
    mock_ml_client,
    monkeypatch,
):
    captured: list[str] = []

    def capture_send(self, to_email: str, otp: str) -> bool:
        captured.append(to_email)
        return True

    monkeypatch.setattr(EmailDeliveryService, "send_login_code", capture_send)

    from app.db.models import MfaMethod, RegistrationStatus, User, UserRole

    user = User(
        username="111550073",
        email="111550073@nycu.edu.tw",
        password_hash=hash_password("PortalPass123!"),
        role=UserRole.USER.value,
        mfa_method=MfaMethod.EMAIL.value,
        registration_status=RegistrationStatus.COMPLETE.value,
        nycu_oauth_subject="111550073",
    )
    db_session.add(user)
    db_session.commit()

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "111550073", "password": "PortalPass123!"},
    )
    assert login.json()["status"] == "mfa_required"
    challenge_id = login.json()["challenge_id"]

    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.status_code == 200
    assert send.json()["delivery_target"] == "111***073@nycu.edu.tw"
    assert captured[-1] == "111550073@nycu.edu.tw"


def test_mfa_send_delivery_failed_returns_503(auth_client: TestClient, seeded_db, monkeypatch):
    monkeypatch.setattr(
        EmailDeliveryService,
        "send_login_code",
        lambda self, _to, _otp: False,
    )
    login = _login(auth_client)
    challenge_id = login.json()["challenge_id"]
    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.status_code == 503
    assert send.json()["status"] == "delivery_failed"
