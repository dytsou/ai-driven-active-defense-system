import secrets

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import RegistrationStatus, User, UserRole
from app.services.email_delivery import EmailDeliveryService


def _patch_email_send(monkeypatch):
    monkeypatch.setattr(
        EmailDeliveryService,
        "send_login_code",
        lambda self, _to, _otp: True,
    )


def _patch_line_send(monkeypatch):
    from app.services.line_client import LineClient

    monkeypatch.setattr(LineClient, "send_otp", lambda self, _uid, _otp: True)


def test_multi_channel_mfa_broadcast(auth_client, seeded_db, fake_redis, monkeypatch):
    _patch_email_send(monkeypatch)
    _patch_line_send(monkeypatch)
    monkeypatch.setattr(settings, "line_mfa_enabled", True)

    user = seeded_db.query(User).filter(User.username == "demo2").one()
    user.line_user_id = "U-demo2-line"
    user.registration_status = RegistrationStatus.COMPLETE.value
    seeded_db.commit()

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo2", "password": settings.seed_demo2_password},
    )
    assert login.json()["status"] == "mfa_required"
    challenge_id = login.json()["challenge_id"]

    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    body = send.json()
    assert body["status"] == "sent"
    assert "LINE" in body["delivery_targets"]
    assert fake_redis.get(f"mfa:otp:{challenge_id}") is not None


def test_partial_mfa_delivery_leaves_no_otp(auth_client, seeded_db, fake_redis, monkeypatch):
    _patch_email_send(monkeypatch)
    monkeypatch.setattr(settings, "line_mfa_enabled", True)

    from app.services.line_client import LineClient

    monkeypatch.setattr(LineClient, "send_otp", lambda self, _uid, _otp: False)

    user = seeded_db.query(User).filter(User.username == "demo2").one()
    user.line_user_id = "U-demo2-line"
    user.registration_status = RegistrationStatus.COMPLETE.value
    seeded_db.commit()

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo2", "password": settings.seed_demo2_password},
    )
    challenge_id = login.json()["challenge_id"]
    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.json()["status"] == "delivery_failed"
    assert fake_redis.get(f"mfa:otp:{challenge_id}") is None
