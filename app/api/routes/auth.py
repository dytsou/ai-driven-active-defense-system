from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, MfaPreferencesUpdate
from app.services.auth_service import AuthService
from app.services.mfa_preferences import mfa_channels_label, mfa_delivery_channels
from app.services.blocklist_manager import BlocklistManager
from app.services.ml_client import MLClient
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
        "mfa_method": mfa_channels_label(user),
        "mfa_line_enabled": user.mfa_line_enabled,
        "line_mfa_available": bool(user.line_user_id),
        "mfa_channels": mfa_delivery_channels(user),
        "registration_status": user.registration_status,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


@router.patch("/me/mfa")
def update_mfa_preferences(
    payload: MfaPreferencesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthService = Depends(get_auth_service),
):
    session_id = request.cookies.get("session_id")
    user = auth.get_current_user(session_id)
    if not user:
        return Response(status_code=401)
    if payload.mfa_line_enabled and not user.line_user_id:
        raise HTTPException(
            status_code=400,
            detail="LINE MFA is unavailable until LINE is bound",
        )
    user.mfa_line_enabled = payload.mfa_line_enabled
    db.commit()
    db.refresh(user)
    return {
        "mfa_line_enabled": user.mfa_line_enabled,
        "mfa_method": mfa_channels_label(user),
        "mfa_channels": mfa_delivery_channels(user),
    }
