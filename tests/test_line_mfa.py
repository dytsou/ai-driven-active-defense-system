import pytest

from app.core.config import settings
from app.db.models import MfaMethod, User
from app.services.line_client import LineClient
from app.services.mfa_service import MfaService


def test_line_client_push_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", False)
    client = LineClient()
    assert client.send_otp("U123", "123456") is False


def test_line_client_push_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)
    monkeypatch.setattr(settings, "line_channel_access_token", "test-token")
    sent = []

    class FakeResponse:
        status_code = 200

    def fake_post(url, headers, json, timeout):
        sent.append((url, json))
        return FakeResponse()

    monkeypatch.setattr("app.services.line_client.httpx.post", fake_post)
    client = LineClient()
    assert client.send_otp("U123", "654321") is True
    assert sent[0][1]["messages"][0]["text"].endswith("654321")


def test_mfa_send_uses_line_for_line_user(auth_client, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)
    demo2 = seeded_db.query(User).filter(User.username == "demo2").one()
    demo2.mfa_method = MfaMethod.LINE.value
    demo2.line_user_id = "U-demo2"
    seeded_db.commit()

    pushed = []
    monkeypatch.setattr(LineClient, "send_otp", lambda self, uid, otp: pushed.append((uid, otp)) or True)

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo2", "password": settings.seed_demo2_password},
    )
    assert login.json()["status"] == "mfa_required"
    challenge_id = login.json()["challenge_id"]

    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.json()["status"] == "sent"
    assert send.json()["message"] == "OTP sent via LINE"
    assert pushed == [("U-demo2", pushed[0][1])]
