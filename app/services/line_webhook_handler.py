import json
import logging
from typing import Any

import redis

from app.core.config import settings
from app.services.line_messaging import LineMessagingService, OTP_REPLY_TEXT

logger = logging.getLogger(__name__)

LINE_MFA_USER_KEY = "line:mfa:user:{line_user_id}"
OTP_RESEND_KEYWORDS = frozenset({"驗證碼", "otp", "code", "登入碼", "mfa"})


class LineWebhookHandler:
    def __init__(
        self,
        redis_client: redis.Redis,
        messaging: LineMessagingService | None = None,
    ):
        self.redis = redis_client
        self.messaging = messaging or LineMessagingService()

    def register_line_mfa_delivery(self, line_user_id: str, challenge_id: str) -> None:
        self.redis.setex(
            LINE_MFA_USER_KEY.format(line_user_id=line_user_id),
            settings.mfa_otp_ttl_seconds,
            challenge_id,
        )

    def clear_line_mfa_delivery(self, line_user_id: str) -> None:
        self.redis.delete(LINE_MFA_USER_KEY.format(line_user_id=line_user_id))

    def handle_payload(self, payload: dict[str, Any]) -> None:
        for event in payload.get("events") or []:
            self._handle_event(event)

    def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "message":
            self._handle_message(event)
        elif event_type == "follow":
            logger.info("LINE follow event user=%s", (event.get("source") or {}).get("userId"))

    def _handle_message(self, event: dict[str, Any]) -> None:
        message = event.get("message") or {}
        if message.get("type") != "text":
            return

        source = event.get("source") or {}
        line_user_id = source.get("userId")
        reply_token = event.get("replyToken")
        if not line_user_id or not reply_token:
            return

        text = (message.get("text") or "").strip()
        if not self._should_reply_with_otp(text, line_user_id):
            return

        challenge_id = self.redis.get(LINE_MFA_USER_KEY.format(line_user_id=line_user_id))
        if not challenge_id:
            self.messaging.reply_text(reply_token, "目前沒有待驗證的登入請求，請先在網頁登入。")
            return

        raw_otp = self.redis.get(f"mfa:otp:{challenge_id}")
        if not raw_otp:
            self.messaging.reply_text(reply_token, "驗證碼已過期，請回到登入頁重新取得。")
            self.clear_line_mfa_delivery(line_user_id)
            return

        otp = raw_otp.split(":", 1)[0]
        self.messaging.reply_text(reply_token, OTP_REPLY_TEXT.format(otp=otp))

    def _should_reply_with_otp(self, text: str, line_user_id: str) -> bool:
        normalized = text.lower()
        if normalized in OTP_RESEND_KEYWORDS or any(keyword in normalized for keyword in OTP_RESEND_KEYWORDS):
            return True
        return bool(self.redis.get(LINE_MFA_USER_KEY.format(line_user_id=line_user_id)))
