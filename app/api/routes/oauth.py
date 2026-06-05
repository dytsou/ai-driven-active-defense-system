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


def finish_nycu_oauth_login(
    *,
    code: str,
    state: str,
    redis_client,
    auth: AuthService,
    ip_address: str,
    attempt_id: str,
) -> NycuOAuthCompletion:
    state_key = f"{OAUTH_STATE_PREFIX}{state}"
    raw_state = redis_client.get(state_key)
    if not raw_state:
        raise NycuOAuthFlowError("invalid_state")
    redis_client.delete(state_key)

    next_path, expected_username = _decode_oauth_state(raw_state)

    oauth = _oauth_service()
    try:
        access_token = oauth.exchange_code(code)
        profile = oauth.fetch_profile(access_token)
    except RuntimeError as exc:
        raise NycuOAuthFlowError(str(exc)) from exc

    if expected_username and profile.username != expected_username:
        raise NycuOAuthFlowError("username_mismatch")

    result = auth.login_via_nycu_oauth(profile.username, profile.email, ip_address, attempt_id)
    return NycuOAuthCompletion(result=result, next_path=next_path)


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

    auth_url, _state = begin_nycu_oauth(
        get_redis_from_request(request),
        next_path=next,
        username=username or None,
    )
    return RedirectResponse(auth_url, status_code=302)


@router.get("/nycu/callback")
def nycu_oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    auth: AuthService = Depends(get_auth_service),
):
    if not nycu_oauth_enabled():
        raise HTTPException(status_code=503, detail="NYCU OAuth is not configured")

    if error:
        return RedirectResponse(f"/?oauth_error={quote(error)}", status_code=302)

    if not code or not state:
        return RedirectResponse("/?oauth_error=missing_code_or_state", status_code=302)

    try:
        completion = finish_nycu_oauth_login(
            code=code,
            state=state,
            redis_client=get_redis_from_request(request),
            auth=auth,
            ip_address=getattr(request.state, "client_ip", "127.0.0.1"),
            attempt_id=getattr(request.state, "attempt_id", "unknown"),
        )
    except NycuOAuthFlowError as exc:
        return RedirectResponse(f"/?oauth_error={quote(str(exc))}", status_code=302)

    response = RedirectResponse(completion.next_path, status_code=302)
    if completion.result.session_id:
        _set_session_cookie(response, completion.result.session_id)
    return response
