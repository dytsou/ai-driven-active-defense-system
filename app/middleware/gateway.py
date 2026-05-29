import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuthGatewayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        attempt_id = request.headers.get("X-Attempt-Id") or str(uuid.uuid4())
        request.state.attempt_id = attempt_id
        request.state.client_ip = self._client_ip(request)

        response = await call_next(request)
        response.headers["X-Attempt-Id"] = attempt_id
        return response

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"
