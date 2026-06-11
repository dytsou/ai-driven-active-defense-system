import base64
import hashlib
import hmac
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

OTP_PUSH_TEXT = "Active Defense 登入驗證碼：{otp}\n（{ttl_min} 分鐘內有效）"
OTP_REPLY_TEXT = "您的 Active Defense 登入驗證碼：{otp}"


class LineMessagingService:
    def enabled(self) -> bool:
        return bool(
            settings.line_mfa_enabled
            and settings.line_channel_access_token
        )

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        secret = settings.line_channel_secret.strip()
        if not secret or not signature:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def push_text(self, line_user_id: str, text: str) -> bool:
        if not self.enabled():
            return False
        return self._post_messages(LINE_PUSH_URL, {"to": line_user_id, "messages": [{"type": "text", "text": text}]})

    def reply_text(self, reply_token: str, text: str) -> bool:
        if not self.enabled():
            return False
        return self._post_messages(
            LINE_REPLY_URL,
            {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]},
        )

    def send_login_otp(self, line_user_id: str, otp: str) -> bool:
        ttl_min = max(1, settings.mfa_otp_ttl_seconds // 60)
        return self.push_text(line_user_id, OTP_PUSH_TEXT.format(otp=otp, ttl_min=ttl_min))

    def _post_messages(self, url: str, payload: dict) -> bool:
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.line_channel_access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
        except httpx.HTTPError:
            logger.exception("LINE Messaging API request failed")
            return False
        if response.status_code != 200:
            logger.warning("LINE Messaging API returned %s: %s", response.status_code, response.text[:200])
            return False
        return True
