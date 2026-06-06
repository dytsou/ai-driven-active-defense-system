import json
import secrets
from dataclasses import dataclass
from urllib.parse import quote

import uuid

import redis
from sqlalchemy.orm import Session

from app.core.config import nycu_oauth_enabled, settings
from app.core.security import hash_password
from app.db.models import RegistrationStatus, User, UserRole
from app.schemas.register import (
    RegisterLineStartResponse,
    RegisterStartResponse,
    RegisterStatusResponse,
)
from app.services.email_delivery import mask_email
from app.services.line_oauth_service import LineOAuthError, LineOAuthService
from app.services.nycu_oauth_service import NycuOAuthService

REG_SESSION_PREFIX = "reg:session:"
REG_NYCU_STATE_PREFIX = "reg:nycu:state:"
REG_LINE_STATE_PREFIX = "reg:line:state:"
REG_BINDING_COOKIE = "reg_binding"


class RegistrationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RegistrationStartBundle:
    response: RegisterStartResponse
    binding: str


@dataclass(frozen=True)
class RegistrationNycuResult:
    registration_token: str
    username: str
    email: str


@dataclass(frozen=True)
class RegistrationLineResult:
    registration_token: str
    line_user_id: str


class RegistrationService:
    def __init__(self, db: Session, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client

    @property
    def session_ttl(self) -> int:
        return settings.registration_session_ttl_seconds

    def _session_key(self, token: str) -> str:
        return f"{REG_SESSION_PREFIX}{token}"

    def _load_session(self, token: str) -> dict:
        raw = self.redis.get(self._session_key(token))
        if not raw:
            raise RegistrationError("invalid_registration_token", "Registration session expired or invalid")
        return json.loads(raw)

    def _save_session(self, token: str, payload: dict) -> None:
        self.redis.setex(self._session_key(token), self.session_ttl, json.dumps(payload))

    def _nycu_redirect_uri(self) -> str:
        return f"{settings.base_url.rstrip('/')}/api/v1/auth/register/nycu/callback"

    def _nycu_service(self) -> NycuOAuthService:
        return NycuOAuthService(
            client_id=settings.nycu_oauth_client_id,
            client_secret=settings.nycu_oauth_client_secret,
            redirect_uri=self._nycu_redirect_uri(),
        )

    def _line_service(self) -> LineOAuthService:
        return LineOAuthService()

    def _verify_binding(self, token: str, binding: str | None) -> None:
        session = self._load_session(token)
        expected = session.get("binding")
        if not binding or not expected or not secrets.compare_digest(binding, expected):
            raise RegistrationError("invalid_state", "Registration session mismatch")

    def start(self, *, resume_subject: str | None = None) -> RegistrationStartBundle:
        if not nycu_oauth_enabled():
            return RegistrationStartBundle(
                response=RegisterStartResponse(status="oauth_error", message="NYCU OAuth is not configured"),
                binding="",
            )

        token = secrets.token_urlsafe(32)
        binding = secrets.token_urlsafe(32)
        session = {
            "step": "pending_oauth",
            "user_id": None,
            "nycu_subject": resume_subject,
            "binding": binding,
        }
        if resume_subject:
            user = (
                self.db.query(User)
                .filter(User.nycu_oauth_subject == resume_subject)
                .one_or_none()
            )
            if user and user.registration_status == RegistrationStatus.COMPLETE.value:
                raise RegistrationError("identity_already_bound", "NYCU account already registered")
            if user:
                session["user_id"] = str(user.id)
                session["step"] = "pending_line"
        self._save_session(token, session)

        state = secrets.token_urlsafe(32)
        auth_url = self._nycu_service().authorization_url(state)
        self.redis.setex(
            f"{REG_NYCU_STATE_PREFIX}{state}",
            self.session_ttl,
            json.dumps({"registration_token": token}),
        )
        return RegistrationStartBundle(
            response=RegisterStartResponse(
                status="started",
                registration_token=token,
                nycu_authorization_url=auth_url,
            ),
            binding=binding,
        )

    def resume_for_subject(self, nycu_subject: str) -> RegistrationStartBundle:
        return self.start(resume_subject=nycu_subject)

    def handle_nycu_callback(self, code: str, state: str, binding: str | None) -> RegistrationNycuResult:
        state_key = f"{REG_NYCU_STATE_PREFIX}{state}"
        raw_state = self.redis.get(state_key)
        if not raw_state:
            raise RegistrationError("invalid_state", "Invalid or expired NYCU OAuth state")
        self.redis.delete(state_key)

        state_payload = json.loads(raw_state)
        token = state_payload["registration_token"]
        self._verify_binding(token, binding)
        session = self._load_session(token)
        if session["step"] not in {"pending_oauth", "pending_line"}:
            raise RegistrationError("invalid_registration_token", "Invalid registration step")

        oauth = self._nycu_service()
        access_token = oauth.exchange_code(code)
        profile = oauth.fetch_profile(access_token)
        subject = profile.username

        existing = (
            self.db.query(User)
            .filter(User.nycu_oauth_subject == subject)
            .one_or_none()
        )
        if existing and existing.registration_status == RegistrationStatus.COMPLETE.value:
            raise RegistrationError("identity_already_bound", "NYCU account already registered")

        user = existing
        if user is None:
            conflict = self.db.query(User).filter(User.username == profile.username).one_or_none()
            if conflict and conflict.registration_status == RegistrationStatus.COMPLETE.value:
                raise RegistrationError("identity_already_bound", "Username already registered")
            if conflict:
                if conflict.nycu_oauth_subject and conflict.nycu_oauth_subject != subject:
                    raise RegistrationError("identity_conflict", "Username bound to another NYCU account")
                session_user_id = session.get("user_id")
                if session_user_id and str(conflict.id) != session_user_id:
                    raise RegistrationError("identity_conflict", "Registration session does not match user")
                user = conflict
            else:
                user = User(
                    username=profile.username,
                    email=profile.email,
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    role=UserRole.USER.value,
                    registration_status=RegistrationStatus.PENDING_LINE.value,
                    nycu_oauth_subject=subject,
                )
                self.db.add(user)
        else:
            user.email = profile.email
            user.nycu_oauth_subject = subject
            user.registration_status = RegistrationStatus.PENDING_LINE.value

        self.db.commit()
        self.db.refresh(user)

        session.update(
            {
                "step": "pending_line",
                "user_id": str(user.id),
                "nycu_subject": subject,
                "username": user.username,
                "email": user.email,
            }
        )
        self._save_session(token, session)
        return RegistrationNycuResult(registration_token=token, username=user.username, email=user.email)

    def start_line(self, registration_token: str, binding: str | None) -> RegisterLineStartResponse:
        from app.core.config import line_login_enabled

        if not line_login_enabled():
            return RegisterLineStartResponse(status="oauth_error", message="LINE Login is not configured")

        self._verify_binding(registration_token, binding)
        session = self._load_session(registration_token)
        if session["step"] != "pending_line":
            raise RegistrationError("invalid_registration_token", "Complete NYCU binding first")

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(16)
        auth_url = self._line_service().authorization_url(state, nonce)
        self.redis.setex(
            f"{REG_LINE_STATE_PREFIX}{state}",
            self.session_ttl,
            json.dumps({"registration_token": registration_token, "nonce": nonce}),
        )
        return RegisterLineStartResponse(status="started", line_authorization_url=auth_url)

    def handle_line_callback(self, code: str, state: str, binding: str | None) -> RegistrationLineResult:
        state_key = f"{REG_LINE_STATE_PREFIX}{state}"
        raw_state = self.redis.get(state_key)
        if not raw_state:
            raise RegistrationError("invalid_state", "Invalid or expired LINE OAuth state")
        self.redis.delete(state_key)

        state_payload = json.loads(raw_state)
        token = state_payload["registration_token"]
        self._verify_binding(token, binding)
        nonce = state_payload.get("nonce")
        session = self._load_session(token)

        line = self._line_service()
        id_token = line.exchange_code(code)
        line_user_id = line.verify_id_token(id_token, nonce=nonce)

        taken = (
            self.db.query(User)
            .filter(User.line_user_id == line_user_id)
            .one_or_none()
        )
        if taken and str(taken.id) != session.get("user_id"):
            raise RegistrationError("line_already_bound", "LINE account already bound to another user")

        user = self.db.query(User).filter(User.id == uuid.UUID(session["user_id"])).one()
        user.line_user_id = line_user_id
        self.db.commit()

        session["step"] = "pending_friend"
        session["line_user_id"] = line_user_id
        self._save_session(token, session)
        return RegistrationLineResult(registration_token=token, line_user_id=line_user_id)

    def confirm_line_friend(self, registration_token: str, binding: str | None) -> RegisterStatusResponse:
        self._verify_binding(registration_token, binding)
        session = self._load_session(registration_token)
        if session["step"] != "pending_friend":
            raise RegistrationError("invalid_registration_token", "Complete LINE binding first")

        user = self.db.query(User).filter(User.id == uuid.UUID(session["user_id"])).one()
        user.registration_status = RegistrationStatus.COMPLETE.value
        self.db.commit()

        session["step"] = "complete"
        self._save_session(registration_token, session)
        return RegisterStatusResponse(status="complete", step="complete", username=user.username)

    def status(self, registration_token: str, binding: str | None = None) -> RegisterStatusResponse:
        try:
            if binding:
                self._verify_binding(registration_token, binding)
            session = self._load_session(registration_token)
        except RegistrationError:
            return RegisterStatusResponse(
                status="invalid_registration_token",
                message="Registration session expired or invalid",
            )

        email = session.get("email")
        return RegisterStatusResponse(
            status="ok",
            step=session.get("step"),
            username=session.get("username"),
            email_masked=mask_email(email) if email else None,
        )

    def frontend_redirect(self, *, token: str, step: str, error: str | None = None) -> str:
        base = settings.frontend_base_url.rstrip("/")
        params = f"token={quote(token)}&step={quote(step)}"
        if error:
            params += f"&error={quote(error)}"
        return f"{base}/register?{params}"
