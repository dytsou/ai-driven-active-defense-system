import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, verify_password
from app.db.models import LoginAttempt, User
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.blocklist_manager import BlocklistManager
from app.services.rate_limiter import RateLimiter
from app.services.session_manager import SessionManager


@dataclass
class LoginResult:
    response: LoginResponse
    session_id: str | None = None
    status_code: int = 200


class AuthService:
    def __init__(
        self,
        db: Session,
        sessions: SessionManager,
        blocklist: BlocklistManager,
        rate_limiter: RateLimiter,
    ):
        self.db = db
        self.sessions = sessions
        self.blocklist = blocklist
        self.rate_limiter = rate_limiter

    def login(self, payload: LoginRequest, ip_address: str, attempt_id: str) -> LoginResult:
        if self.blocklist.is_blocked(ip_address):
            self._record_attempt(payload.username, ip_address, success=False, action="blocked")
            return LoginResult(
                response=LoginResponse(status="blocked", message="IP address is blocked"),
                status_code=403,
            )

        if not self.rate_limiter.check_and_increment(ip_address):
            return LoginResult(
                response=LoginResponse(status="rate_limited", message="Too many login attempts"),
                status_code=429,
            )

        user = self.db.query(User).filter(User.username == payload.username).one_or_none()
        password_hash = user.password_hash if user else DUMMY_HASH
        credentials_valid = user is not None and verify_password(payload.password, password_hash)

        if not credentials_valid:
            self._record_attempt(payload.username, ip_address, success=False, action="invalid")
            return LoginResult(
                response=LoginResponse(status="invalid_credentials", message="Invalid username or password"),
                status_code=401,
            )

        self._record_attempt(payload.username, ip_address, success=True, action="allow")
        session_id = self.sessions.create_session(str(user.id), user.username)
        return LoginResult(
            response=LoginResponse(status="success", message="Login successful"),
            session_id=session_id,
            status_code=200,
        )

    def get_current_user(self, session_id: str | None) -> User | None:
        if not session_id:
            return None
        data = self.sessions.get_session(session_id)
        if not data:
            return None
        user_id = uuid.UUID(data["user_id"])
        return self.db.query(User).filter(User.id == user_id).one_or_none()

    def _record_attempt(
        self,
        username: str,
        ip_address: str,
        *,
        success: bool,
        action: str,
    ) -> None:
        self.db.add(
            LoginAttempt(
                username=username,
                ip_address=ip_address,
                success=success,
                action_taken=action,
            )
        )
        self.db.commit()
