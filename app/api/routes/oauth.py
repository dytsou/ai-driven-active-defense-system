import json
import secrets
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import nycu_oauth_enabled, settings
from app.db.session import get_db
from app.services.auth_service import AuthService, LoginResult
from app.services.blocklist_manager import BlocklistManager
from app.services.ml_client import MLClient
from app.services.nycu_oauth_service import NycuOAuthService
from app.services.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_from_request
from app.services.session_manager import SessionManager
from app.services.threat_analyzer import ThreatAnalyzer

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])

OAUTH_STATE_TTL_SECONDS = 600
OAUTH_STATE_PREFIX = "oauth:nycu:state:"
LOCAL_PASSWORD_USERNAMES = frozenset({"admin", "demo1", "demo2"})


class NycuOAuthFlowError(Exception):
    pass


@dataclass(frozen=True)
class NycuOAuthCompletion:
    result: LoginResult
    next_path: str


def should_use_nycu_oauth(username: str) -> bool:
    return nycu_oauth_enabled() and username.strip() not in LOCAL_PASSWORD_USERNAMES


def nycu_oauth_redirect_uri() -> str:
    return f"{settings.base_url.rstrip('/')}/api/v1/auth/oauth/nycu/callback"


def _oauth_service() -> NycuOAuthService:
    return NycuOAuthService(
        client_id=settings.nycu_oauth_client_id,
        client_secret=settings.nycu_oauth_client_secret,
        redirect_uri=nycu_oauth_redirect_uri(),
    )


def _safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/me"
    return value


def _encode_oauth_state(*, next_path: str, username: str | None = None) -> str:
    payload = {"next": _safe_next_path(next_path)}
    if username:
        payload["username"] = username.strip()
    return json.dumps(payload)


def _parse_oauth_state(raw: str) -> dict:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return {"next": _safe_next_path(raw)}


def _decode_oauth_state(raw: str) -> tuple[str, str | None]:
    payload = _parse_oauth_state(raw)
    return _safe_next_path(payload.get("next")), payload.get("username")


def begin_nycu_oauth(
    redis_client,
    *,
    next_path: str = "/me",
    username: str | None = None,
) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    auth_url = _oauth_service().authorization_url(state, login_hint=username)
    redis_client.setex(
        f"{OAUTH_STATE_PREFIX}{state}",
        OAUTH_STATE_TTL_SECONDS,
        _encode_oauth_state(next_path=next_path, username=username),
    )
    return auth_url, state


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=3600,
    )


def get_auth_service(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthService:
    redis_client = get_redis_from_request(request)
    threat_analyzer = getattr(request.app.state, "threat_analyzer", None) or ThreatAnalyzer(
        ml_client=MLClient()
    )
    return AuthService(
        db=db,
        sessions=SessionManager(redis_client),
        blocklist=BlocklistManager(redis_client),
        rate_limiter=RateLimiter(redis_client),
        threat_analyzer=threat_analyzer,
        redis=redis_client,
    )


@router.get("/nycu/start")
def nycu_oauth_start(request: Request, next: str = "/me", username: str = ""):
    if not nycu_oauth_enabled():
        raise HTTPException(status_code=503, detail="NYCU OAuth is not configured")
    return RedirectResponse("/register", status_code=302)


@router.get("/nycu/callback")
def nycu_oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    auth: AuthService = Depends(get_auth_service),
):
    if error:
        return RedirectResponse(f"/register?error={quote(error)}", status_code=302)
    return RedirectResponse("/register?error=use_registration_flow", status_code=302)
