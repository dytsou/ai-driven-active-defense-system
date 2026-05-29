from starlette.requests import Request


def resolve_client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    # Only honor XFF when trust_proxy_headers is true and a trusted proxy strips
    # client-supplied values before appending the real client IP (see README).
    if trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"
