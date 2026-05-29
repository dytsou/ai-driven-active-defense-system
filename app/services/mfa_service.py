import json
import random
import smtplib
from email.message import EmailMessage

import redis

from app.core.config import settings
from app.db.models import User
from app.db.models import MfaMethod
from app.schemas.auth import MfaResponse
from app.services.line_client import LineClient


class MfaService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def store_challenge(self, challenge_id: str, user: User, ip_address: str) -> None:
        payload = json.dumps({"user_id": str(user.id), "username": user.username, "ip": ip_address})
        self.redis.setex(f"mfa:challenge:{challenge_id}", settings.mfa_otp_ttl_seconds, payload)

    def send_otp(self, challenge_id: str, user: User) -> MfaResponse:
        if not self.redis.exists(f"mfa:challenge:{challenge_id}"):
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid")

        otp = f"{random.randint(0, 999999):06d}"
        self.redis.setex(
            f"mfa:otp:{challenge_id}",
            settings.mfa_otp_ttl_seconds,
            f"{otp}:0",
        )
        if user.mfa_method == MfaMethod.LINE.value and settings.line_mfa_enabled:
            line_user_id = user.line_user_id or user.username
            if LineClient().send_otp(line_user_id, otp):
                return MfaResponse(status="sent", message="OTP sent via LINE")
            return MfaResponse(status="delivery_failed", message="LINE delivery failed")

        self._send_email(user.email, otp)
        return MfaResponse(status="sent", message="OTP sent via email")

    def verify_otp(self, challenge_id: str, otp: str) -> tuple[MfaResponse, str | None]:
        challenge_key = f"mfa:challenge:{challenge_id}"
        otp_key = f"mfa:otp:{challenge_id}"
        if not self.redis.exists(challenge_key):
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid"), None

        raw = self.redis.get(otp_key)
        if not raw:
            return MfaResponse(status="invalid_challenge", message="OTP not sent"), None

        expected, attempts = raw.split(":")
        attempts = int(attempts)
        if attempts >= settings.mfa_max_attempts:
            self.redis.delete(challenge_key)
            self.redis.delete(otp_key)
            return MfaResponse(status="challenge_locked", message="Too many invalid OTP attempts"), None

        if otp != expected:
            attempts += 1
            self.redis.setex(otp_key, settings.mfa_otp_ttl_seconds, f"{expected}:{attempts}")
            if attempts >= settings.mfa_max_attempts:
                self.redis.delete(challenge_key)
                self.redis.delete(otp_key)
                return MfaResponse(status="challenge_locked", message="Too many invalid OTP attempts"), None
            return MfaResponse(status="invalid_otp", message="Invalid OTP"), None

        challenge = json.loads(self.redis.get(challenge_key))
        self.redis.delete(challenge_key)
        self.redis.delete(otp_key)
        return MfaResponse(status="success", message="MFA verified"), challenge["user_id"]

    def _send_email(self, to_email: str, otp: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Your Active Defense login code"
        message["From"] = settings.smtp_from
        message["To"] = to_email
        message.set_content(f"Your verification code is: {otp}")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.send_message(message)
        except OSError:
            # Demo mode: Mailhog may be unavailable during unit tests.
            pass
