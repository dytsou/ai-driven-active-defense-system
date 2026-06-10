from app.core.config import settings
from app.db.models import RegistrationStatus, User
from app.services.email_delivery import EmailDeliveryService
from app.services.line_client import LineClient

NORMAL_KEYSTROKE = {
    "keystroke": {
        "present": True,
        "timing": {
            "dwell_times": [95, 92, 98],
            "flight_times": [110, 108, 112],
        },
    }
}


def test_mfa_skips_line_when_user_disabled(auth_client, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)
    monkeypatch.setattr(settings, "mfa_auto_send", False)

    user = seeded_db.query(User).filter(User.username == "demo2").one()
    user.line_user_id = "U-demo2-line"
    user.mfa_line_enabled = False
    user.registration_status = RegistrationStatus.COMPLETE.value
    seeded_db.commit()

    pushed = []
    monkeypatch.setattr(
        EmailDeliveryService,
        "send_login_code",
        lambda self, _to, _otp: (True, None),
    )
    monkeypatch.setattr(
        LineClient,
        "send_otp",
        lambda self, uid, otp: pushed.append((uid, otp)) or True,
    )

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo2", "password": settings.seed_demo2_password},
    )
    challenge_id = login.json()["challenge_id"]
    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    body = send.json()

    assert body["status"] == "sent"
    assert "LINE" not in body["delivery_targets"]
    assert pushed == []


def test_patch_me_mfa_preferences(auth_client, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)

    user = seeded_db.query(User).filter(User.username == "demo1").one()
    user.line_user_id = "U-demo1-line"
    user.mfa_line_enabled = True
    seeded_db.commit()

    login = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo1",
            "password": settings.seed_demo1_password,
            **NORMAL_KEYSTROKE,
        },
    )
    assert login.json()["status"] == "success"

    me = auth_client.get("/api/v1/auth/me")
    assert me.json()["mfa_line_enabled"] is True
    assert me.json()["mfa_method"] == "both"

    updated = auth_client.patch(
        "/api/v1/auth/me/mfa",
        json={"mfa_line_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["mfa_method"] == "email"

    me_after = auth_client.get("/api/v1/auth/me")
    assert me_after.json()["mfa_line_enabled"] is False
