import re
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import settings
from app.services.nycu_oauth_service import NYCU_LOGIN_URL, nycu_login_url


class NycuOAuthHttpError(Exception):
    pass


INVALID_CREDENTIALS_MARKERS = (
    "請檢查帳號、密碼是否有錯誤",
    "Invalid username or password",
)


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    if not match:
        raise NycuOAuthHttpError("NYCU login page missing CSRF token")
    return match.group(1)


def _login_failed(html: str) -> bool:
    return any(marker in html for marker in INVALID_CREDENTIALS_MARKERS)


def _extract_hidden_fields(html: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', html))


def _extract_code(response: httpx.Response, redirect_uri: str) -> str:
    redirect_prefix = redirect_uri.split("?")[0]
    final_url = str(response.url)
    if not final_url.startswith(redirect_prefix):
        raise NycuOAuthHttpError(f"OAuth callback missing authorization code ({final_url})")
    code = parse_qs(urlparse(final_url).query).get("code", [None])[0]
    if not code:
        raise NycuOAuthHttpError("OAuth callback missing authorization code")
    return code


def _approve_oauth_if_needed(client: httpx.Client, response: httpx.Response) -> httpx.Response:
    if "/o/authorize/" not in str(response.url):
        return response

    form_data = _extract_hidden_fields(response.text)
    form_data["csrfmiddlewaretoken"] = _extract_csrf(response.text)
    return client.post(
        str(response.url),
        data=form_data,
        headers={"Referer": str(response.url)},
    )


def collect_authorization_code(
    authorization_url: str,
    *,
    username: str,
    password: str,
    redirect_uri: str,
    timeout: float | None = None,
) -> str:
    login_url = nycu_login_url(authorization_url)
    request_timeout = timeout or settings.nycu_oauth_http_timeout_seconds

    with httpx.Client(follow_redirects=True, timeout=request_timeout) as client:
        login_page = client.get(login_url)
        csrf = _extract_csrf(login_page.text)
        response = client.post(
            NYCU_LOGIN_URL,
            data={
                "csrfmiddlewaretoken": csrf,
                "username": username,
                "password": password,
                "next": authorization_url,
            },
            headers={"Referer": login_url},
        )
        if _login_failed(response.text):
            raise NycuOAuthHttpError("Invalid NYCU portal credentials")

        response = _approve_oauth_if_needed(client, response)
        if _login_failed(response.text):
            raise NycuOAuthHttpError("Invalid NYCU portal credentials")

        return _extract_code(response, redirect_uri)
