from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import nycu_oauth_enabled, settings
from app.db.session import get_db
from app.schemas.register import (
    RegisterCompleteRequest,
    RegisterLineStartRequest,
    RegisterLineStartResponse,
    RegisterStartResponse,
    RegisterStatusResponse,
)
from app.services.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_from_request
from app.services.registration_service import (
    REG_BINDING_COOKIE,
    RegistrationError,
    RegistrationService,
)

router = APIRouter(prefix="/api/v1/auth/register", tags=["register"])


def get_registration_service(request: Request, db: Session = Depends(get_db)) -> RegistrationService:
    return RegistrationService(db=db, redis_client=get_redis_from_request(request))


def _check_register_rate_limit(request: Request) -> None:
    ip_address = getattr(request.state, "client_ip", "127.0.0.1")
    limiter = RateLimiter(get_redis_from_request(request))
    if not limiter.check_and_increment(
        ip_address, settings.rate_limit_register_per_min, namespace="register"
    ):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Too many registration attempts")


def _reg_binding(request: Request) -> str | None:
    return request.cookies.get(REG_BINDING_COOKIE)


@router.post("/start", response_model=RegisterStartResponse)
def register_start(
    request: Request,
    response: Response,
    reg: RegistrationService = Depends(get_registration_service),
):
    _check_register_rate_limit(request)
    bundle = reg.start()
    if bundle.binding:
        response.set_cookie(
            key=REG_BINDING_COOKIE,
            value=bundle.binding,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            max_age=settings.registration_session_ttl_seconds,
        )
    return bundle.response


@router.get("/nycu/callback")
def register_nycu_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    reg: RegistrationService = Depends(get_registration_service),
):
    if error:
        return RedirectResponse(f"/register?error={quote(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse("/register?error=missing_code_or_state", status_code=302)
    try:
        result = reg.handle_nycu_callback(code, state, _reg_binding(request))
    except RegistrationError as exc:
        return RedirectResponse(f"/register?error={quote(exc.code)}", status_code=302)
    url = reg.frontend_redirect(token=result.registration_token, step="line")
    return RedirectResponse(url, status_code=302)


@router.post("/line/start", response_model=RegisterLineStartResponse)
def register_line_start(
    request: Request,
    payload: RegisterLineStartRequest,
    reg: RegistrationService = Depends(get_registration_service),
):
    _check_register_rate_limit(request)
    try:
        return reg.start_line(payload.registration_token, _reg_binding(request))
    except RegistrationError as exc:
        return RegisterLineStartResponse(status=exc.code, message=exc.message)


@router.get("/line/callback")
def register_line_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    reg: RegistrationService = Depends(get_registration_service),
):
    if error:
        return RedirectResponse(f"/register?error={quote(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse("/register?error=missing_code_or_state", status_code=302)
    try:
        result = reg.handle_line_callback(code, state, _reg_binding(request))
    except RegistrationError as exc:
        return RedirectResponse(f"/register?error={quote(exc.code)}", status_code=302)
    url = reg.frontend_redirect(token=result.registration_token, step="friend")
    return RedirectResponse(url, status_code=302)


@router.post("/complete", response_model=RegisterStatusResponse)
def register_complete(
    request: Request,
    payload: RegisterCompleteRequest,
    reg: RegistrationService = Depends(get_registration_service),
):
    _check_register_rate_limit(request)
    try:
        return reg.confirm_line_friend(payload.registration_token, _reg_binding(request))
    except RegistrationError as exc:
        return RegisterStatusResponse(status=exc.code, message=exc.message)


@router.get("/status", response_model=RegisterStatusResponse)
def register_status(
    request: Request,
    token: str = "",
    reg: RegistrationService = Depends(get_registration_service),
):
    _check_register_rate_limit(request)
    if not token:
        return RegisterStatusResponse(status="invalid_registration_token", message="Missing token")
    return reg.status(token, _reg_binding(request))
