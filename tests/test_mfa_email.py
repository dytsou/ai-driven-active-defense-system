import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def _login(auth_client: TestClient, **extra):
    payload = {"username": "demo1", "password": settings.seed_demo1_password, **extra}
    return auth_client.post("/api/v1/auth/login", json=payload)


def test_mfa_flow_issues_and_verifies_otp(
    auth_client: TestClient, seeded_db, fake_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.mfa_service.MfaService._send_email",
        lambda self, _to, _otp: True,
    )
    login = _login(auth_client)
    assert login.json()["status"] == "mfa_required"
    challenge_id = login.json()["challenge_id"]

    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.status_code == 200
    assert send.json()["status"] == "sent"

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
    monkeypatch.setattr(
        "app.services.mfa_service.MfaService._send_email",
        lambda self, _to, _otp: True,
    )
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
