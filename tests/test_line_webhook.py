import base64
import hashlib
import hmac
import json

from app.core.config import settings
from app.services.line_messaging import LineMessagingService


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_verify_webhook_signature_with_config(monkeypatch):
    monkeypatch.setattr(settings, "line_channel_secret", "line-channel-secret")
    body = b'{"events":[]}'
    signature = _sign(body, "line-channel-secret")
    assert LineMessagingService().verify_webhook_signature(body, signature) is True
    assert LineMessagingService().verify_webhook_signature(body, "bad") is False


def test_webhook_replies_otp_on_message(auth_client, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)
    monkeypatch.setattr(settings, "line_channel_access_token", "test-token")
    monkeypatch.setattr(settings, "line_channel_secret", "line-channel-secret")

    from app.db.models import User

    user = seeded_db.query(User).filter(User.username == "demo2").one()
    user.line_user_id = "U-demo2-line"
    seeded_db.commit()

    fake_redis.setex("line:mfa:user:U-demo2-line", 300, "challenge-123")
    fake_redis.setex("mfa:otp:challenge-123", 300, "654321:0")

    replies = []
    monkeypatch.setattr(
        LineMessagingService,
        "reply_text",
        lambda self, reply_token, text: replies.append((reply_token, text)) or True,
    )

    payload = {
        "events": [
            {
                "type": "message",
                "replyToken": "reply-token-1",
                "source": {"type": "user", "userId": "U-demo2-line"},
                "message": {"type": "text", "text": "驗證碼"},
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    response = auth_client.post(
        "/api/v1/line/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": _sign(body, "line-channel-secret"),
        },
    )
    assert response.status_code == 200
    assert replies == [("reply-token-1", "您的 Active Defense 登入驗證碼：654321")]


def test_webhook_rejects_invalid_signature(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "line_channel_secret", "line-channel-secret")
    response = auth_client.post(
        "/api/v1/line/webhook",
        json={"events": []},
        headers={"X-Line-Signature": "invalid"},
    )
    assert response.status_code == 400


def test_mfa_send_registers_line_webhook_delivery(auth_client, seeded_db, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "line_mfa_enabled", True)
    monkeypatch.setattr(settings, "line_channel_access_token", "test-token")
    monkeypatch.setattr(settings, "mfa_auto_send", False)

    from app.db.models import User
    from app.services.email_delivery import EmailDeliveryService

    user = seeded_db.query(User).filter(User.username == "demo2").one()
    user.line_user_id = "U-demo2-line"
    seeded_db.commit()

    monkeypatch.setattr(
        EmailDeliveryService,
        "send_login_code",
        lambda self, _to, _otp: (True, None),
    )
    monkeypatch.setattr(LineMessagingService, "send_login_otp", lambda self, uid, otp: True)

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "demo2", "password": settings.seed_demo2_password},
    )
    challenge_id = login.json()["challenge_id"]
    send = auth_client.post("/api/v1/auth/mfa/send", json={"challenge_id": challenge_id})
    assert send.json()["status"] == "sent"
    assert fake_redis.get("line:mfa:user:U-demo2-line") == challenge_id
