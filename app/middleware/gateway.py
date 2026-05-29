import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.client_ip import resolve_client_ip
from app.core.config import settings


class AuthGatewayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        attempt_id = str(uuid.uuid4())
        request.state.attempt_id = attempt_id
        request.state.client_ip = resolve_client_ip(
            request, trust_proxy_headers=settings.trust_proxy_headers
        )

        response = await call_next(request)
        response.headers["X-Attempt-Id"] = attempt_id
        return response
