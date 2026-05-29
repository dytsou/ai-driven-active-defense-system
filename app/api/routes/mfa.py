from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
import uuid

from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import MfaResponse, MfaSendRequest, MfaVerifyRequest
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.mfa_service import MfaService
from app.services.redis_client import get_redis_from_request
from app.services.session_manager import SessionManager
from app.api.routes.auth import get_auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["mfa"])


def get_mfa_service(request: Request) -> MfaService:
    return MfaService(get_redis_from_request(request))


@router.post("/mfa/send", response_model=MfaResponse)
def mfa_send(
    payload: MfaSendRequest,
    request: Request,
    db: Session = Depends(get_db),
    mfa: MfaService = Depends(get_mfa_service),
):
    user = _challenge_user(db, payload.challenge_id, request)
    if not user:
        return MfaResponse(status="invalid_challenge", message="Challenge expired or invalid")
    return mfa.send_otp(payload.challenge_id, user)


@router.post("/mfa/verify", response_model=MfaResponse)
def mfa_verify(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    mfa: MfaService = Depends(get_mfa_service),
    auth: AuthService = Depends(get_auth_service),
):
    result, user_id = mfa.verify_otp(payload.challenge_id, payload.otp)
    if result.status != "success" or not user_id:
        response.status_code = 400
        return result

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).one()
    sessions = SessionManager(get_redis_from_request(request))
    session_id = sessions.create_session(str(user.id), user.username)
    response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax", max_age=3600)
    EventService(db).record(
        event_type="login_success",
        actor_username=user.username,
        ip_address=getattr(request.state, "client_ip", None),
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
