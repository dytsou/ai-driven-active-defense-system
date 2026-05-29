from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import AuthService
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

    if result.session_id:
        response.set_cookie(
            key="session_id",
            value=result.session_id,
            httponly=True,
            samesite="lax",
            max_age=3600,
        )

    response.status_code = result.status_code
    return result.response


@router.get("/me")
def me(request: Request, auth: AuthService = Depends(get_auth_service)):
    session_id = request.cookies.get("session_id")
    user = auth.get_current_user(session_id)
    if not user:
        return Response(status_code=401)
    return {"username": user.username, "role": user.role}
