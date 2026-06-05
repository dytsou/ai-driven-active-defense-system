from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.routes.oauth import (
    begin_nycu_oauth,
    finish_nycu_oauth_login,
    nycu_oauth_redirect_uri,
    should_use_nycu_oauth,
)
from app.core.config import nycu_oauth_enabled, settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import AuthService
from app.services.blocklist_manager import BlocklistManager
from app.services.ml_client import MLClient
from app.services.nycu_oauth_http import NycuOAuthHttpError, collect_authorization_code
from app.services.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_from_request
from app.services.session_manager import SessionManager
from app.services.threat_analyzer import ThreatAnalyzer

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_threat_analyzer(request: Request) -> ThreatAnalyzer:
    analyzer = getattr(request.app.state, "threat_analyzer", None)
    if analyzer is not None:
        return analyzer
    return ThreatAnalyzer(ml_client=MLClient())


def get_auth_service(
    request: Request,
    db: Session = Depends(get_db),
    threat_analyzer: ThreatAnalyzer = Depends(get_threat_analyzer),
) -> AuthService:
    redis_client = get_redis_from_request(request)
    return AuthService(
        db=db,
        sessions=SessionManager(redis_client),
        blocklist=BlocklistManager(redis_client),
        rate_limiter=RateLimiter(redis_client),
        threat_analyzer=threat_analyzer,
        redis=redis_client,
    )


def _apply_session_cookie(response: Response, session_id: str | None) -> None:
    if not session_id:
        return
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=3600,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
):
    attempt_id = getattr(request.state, "attempt_id", "unknown")
    ip_address = getattr(request.state, "client_ip", "127.0.0.1")

    if should_use_nycu_oauth(payload.username):
        if not nycu_oauth_enabled():
            return LoginResponse(
                status="oauth_error",
                message="NYCU OAuth 未設定",
            )

        redis_client = get_redis_from_request(request)
        username = payload.username.strip()
        auth_url, state = begin_nycu_oauth(redis_client, username=username)

        try:
            code = collect_authorization_code(
                auth_url,
                username=username,
                password=payload.password,
                redirect_uri=nycu_oauth_redirect_uri(),
            )
            completion = finish_nycu_oauth_login(
                code=code,
                state=state,
                redis_client=redis_client,
                auth=auth,
                ip_address=ip_address,
                attempt_id=attempt_id,
            )
        except NycuOAuthHttpError as exc:
            if "Invalid NYCU portal credentials" in str(exc):
                return LoginResponse(
                    status="invalid_credentials",
                    message="NYCU 入口網站帳號或密碼錯誤，請確認 Portal 密碼",
                )
            return LoginResponse(
                status="oauth_error",
                message="NYCU 登入失敗，請稍後再試",
            )

        _apply_session_cookie(response, completion.result.session_id)
        response.status_code = completion.result.status_code
        return completion.result.response

    result = auth.login(payload, ip_address, attempt_id)
    _apply_session_cookie(response, result.session_id)
    response.status_code = result.status_code
    return result.response


@router.get("/me")
def me(request: Request, auth: AuthService = Depends(get_auth_service)):
    session_id = request.cookies.get("session_id")
    user = auth.get_current_user(session_id)
    if not user:
        return Response(status_code=401)
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "mfa_method": user.mfa_method,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
