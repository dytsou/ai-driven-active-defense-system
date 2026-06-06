import json
import secrets

import redis

from app.core.config import settings
from app.db.models import User
from app.schemas.auth import MfaResponse
from app.services.email_delivery import EmailDeliveryService, mask_email
from app.services.line_client import LineClient


class MfaService:
    def __init__(
        self,
        redis_client: redis.Redis,
        email_delivery: EmailDeliveryService | None = None,
    ):
        self.redis = redis_client
        self.email_delivery = email_delivery or EmailDeliveryService()

    def store_challenge(self, challenge_id: str, user: User, ip_address: str) -> None:
        payload = json.dumps({"user_id": str(user.id), "username": user.username, "ip": ip_address})
        ttl = settings.mfa_otp_ttl_seconds
        self.redis.setex(f"mfa:challenge:{challenge_id}", ttl, payload)
        self.redis.setex(f"mfa:pending:user:{user.id}", ttl, challenge_id)

    def active_challenge_id(self, user_id: str) -> str | None:
        pending = self.redis.get(f"mfa:pending:user:{user_id}")
        if not pending:
            return None
        if not self.redis.exists(f"mfa:challenge:{pending}"):
            self.redis.delete(f"mfa:pending:user:{user_id}")
            return None
        return pending

    def challenge_matches_ip(self, challenge_id: str, ip_address: str) -> bool:
        raw = self.redis.get(f"mfa:challenge:{challenge_id}")
        if not raw:
            return False
        challenge = json.loads(raw)
        bound_ip = challenge.get("ip")
        return not bound_ip or bound_ip == ip_address

    def send_otp(self, challenge_id: str, user: User, *, ip_address: str | None = None) -> MfaResponse:
        if not self.redis.exists(f"mfa:challenge:{challenge_id}"):
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid")
        if ip_address and not self.challenge_matches_ip(challenge_id, ip_address):
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid")

        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_key = f"mfa:otp:{challenge_id}"
        attempts = 0
        existing = self.redis.get(otp_key)
        if existing:
            _, attempts = existing.split(":", 1)
            attempts = int(attempts)

        channels: list[tuple[str, str, bool]] = []
        delivery_targets: list[str] = []

        if user.email:
            channels.append(("email", user.email, False))
            delivery_targets.append(mask_email(user.email))

        if user.line_user_id and settings.line_mfa_enabled:
            channels.append(("line", user.line_user_id, False))
            delivery_targets.append("LINE")

        if not channels:
            return MfaResponse(status="delivery_failed", message="No MFA channels bound")

        for idx, (kind, target, _) in enumerate(channels):
            if kind == "email":
                channels[idx] = (kind, target, self.email_delivery.send_login_code(target, otp))
            else:
                channels[idx] = (kind, target, LineClient().send_otp(target, otp))

        if not all(ok for _, _, ok in channels):
            self.redis.delete(otp_key)
            return MfaResponse(status="delivery_failed", message="MFA delivery failed")

        self.redis.setex(otp_key, settings.mfa_otp_ttl_seconds, f"{otp}:{attempts}")
        primary_email = mask_email(user.email) if user.email else None
        return MfaResponse(
            status="sent",
            message="OTP sent to bound channels",
            delivery_target=primary_email,
            delivery_targets=delivery_targets,
        )

    def verify_otp(self, challenge_id: str, otp: str, ip_address: str | None = None) -> tuple[MfaResponse, str | None]:
        challenge_key = f"mfa:challenge:{challenge_id}"
        otp_key = f"mfa:otp:{challenge_id}"
        if not self.redis.exists(challenge_key):
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid"), None

        challenge_raw = self.redis.get(challenge_key)
        if not challenge_raw:
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid"), None

        challenge = json.loads(challenge_raw)
        if ip_address and challenge.get("ip") and challenge["ip"] != ip_address:
            return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid"), None

        raw = self.redis.get(otp_key)
        if not raw:
            return MfaResponse(status="invalid_challenge", message="OTP not sent"), None

        expected, attempts = raw.split(":", 1)
        attempts = int(attempts)
        if attempts >= settings.mfa_max_attempts:
            self.redis.delete(challenge_key)
            self.redis.delete(otp_key)
            return MfaResponse(status="challenge_locked", message="Too many invalid OTP attempts"), None

        if not secrets.compare_digest(otp, expected):
            attempts += 1
            self.redis.setex(otp_key, settings.mfa_otp_ttl_seconds, f"{expected}:{attempts}")
            if attempts >= settings.mfa_max_attempts:
                self.redis.delete(challenge_key)
                self.redis.delete(otp_key)
                return MfaResponse(status="challenge_locked", message="Too many invalid OTP attempts"), None
            return MfaResponse(status="invalid_otp", message="Invalid OTP"), None

        self.redis.delete(challenge_key)
        self.redis.delete(otp_key)
        self.redis.delete(f"mfa:pending:user:{challenge['user_id']}")
        return MfaResponse(status="success", message="MFA verified"), challenge["user_id"]
