from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
import uuid

from app.db.models import User
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import MfaResponse, MfaSendRequest, MfaVerifyRequest
from app.services.blocklist_manager import BlocklistManager
from app.services.event_service import EventService
from app.services.mfa_service import MfaService
from app.services.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_from_request
from app.services.session_manager import SessionManager

router = APIRouter(prefix="/api/v1/auth", tags=["mfa"])


def get_mfa_service(request: Request) -> MfaService:
    return MfaService(get_redis_from_request(request))


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", "127.0.0.1")


def _mfa_guards(request: Request, challenge_id: str | None = None) -> MfaResponse | None:
    redis_client = get_redis_from_request(request)
    ip_address = _client_ip(request)
    if BlocklistManager(redis_client).is_blocked(ip_address):
        return MfaResponse(status="blocked", message="IP address is blocked")
    return None


@router.post("/mfa/send", response_model=MfaResponse)
def mfa_send(
    payload: MfaSendRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    mfa: MfaService = Depends(get_mfa_service),
):
    blocked = _mfa_guards(request, payload.challenge_id)
    if blocked:
        response.status_code = 403
        return blocked

    redis_client = get_redis_from_request(request)
    ip_address = _client_ip(request)
    limiter = RateLimiter(redis_client)
    if not limiter.check_and_increment(
        ip_address, settings.rate_limit_mfa_send_per_min, namespace="mfa_send"
    ):
        response.status_code = 429
        return MfaResponse(status="rate_limited", message="Too many MFA send requests")

    challenge_key = f"challenge:{payload.challenge_id}"
    if not limiter.check_and_increment(
        challenge_key,
        settings.rate_limit_mfa_send_per_challenge,
        namespace="mfa_send_challenge",
    ):
        response.status_code = 429
        return MfaResponse(status="rate_limited", message="Too many OTP requests for this challenge")

    user = _challenge_user(db, payload.challenge_id, request)
    if not user:
        response.status_code = 400
        return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid")
    return mfa.send_otp(payload.challenge_id, user)


@router.post("/mfa/verify", response_model=MfaResponse)
def mfa_verify(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    mfa: MfaService = Depends(get_mfa_service),
):
    blocked = _mfa_guards(request, payload.challenge_id)
    if blocked:
        response.status_code = 403
        return blocked

    redis_client = get_redis_from_request(request)
    ip_address = _client_ip(request)
    limiter = RateLimiter(redis_client)
    if not limiter.check_and_increment(
        ip_address, settings.rate_limit_mfa_verify_per_min, namespace="mfa_verify"
    ):
        response.status_code = 429
        return MfaResponse(status="rate_limited", message="Too many MFA verify attempts")

    result, user_id = mfa.verify_otp(payload.challenge_id, payload.otp, ip_address=ip_address)
    if result.status != "success" or not user_id:
        response.status_code = 400
        return result

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).one()
    sessions = SessionManager(redis_client)
    session_id = sessions.create_session(str(user.id), user.username)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=3600,
    )
    EventService(db).record(
        event_type="login_success",
        actor_username=user.username,
        ip_address=ip_address,
        payload={"via": "mfa", "challenge_id": payload.challenge_id},
    )
    return MfaResponse(status="success", message="Login successful")


def _challenge_user(db: Session, challenge_id: str, request: Request) -> User | None:
    redis_client = get_redis_from_request(request)
    raw = redis_client.get(f"mfa:challenge:{challenge_id}")
    if not raw:
        return None
    import json

    data = json.loads(raw)
    return db.query(User).filter(User.id == uuid.UUID(data["user_id"])).one_or_none()
