from dataclasses import dataclass
from urllib.parse import quote, urlencode

import httpx

AUTH_URL = "https://id.nycu.edu.tw/o/authorize/"
NYCU_LOGIN_URL = "https://id.nycu.edu.tw/accounts/login/"


def nycu_login_url(authorization_url: str) -> str:
    return f"{NYCU_LOGIN_URL}?next={quote(authorization_url, safe='')}"


TOKEN_URL = "https://id.nycu.edu.tw/o/token/"
PROFILE_URL = "https://id.nycu.edu.tw/api/profile/"
OAUTH_SCOPE = "profile"


@dataclass(frozen=True)
class NycuOAuthProfile:
    username: str
    email: str


class NycuOAuthService:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def authorization_url(self, state: str, login_hint: str | None = None) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": OAUTH_SCOPE,
            "state": state,
        }
        hint = (login_hint or "").strip()
        if hint:
            params["login_hint"] = hint
        query = urlencode(params)
        return f"{AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> str:
        response = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"NYCU token exchange failed: {response.status_code} {response.text}")
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("NYCU token exchange returned no access_token")
        return access_token

    def fetch_profile(self, access_token: str) -> NycuOAuthProfile:
        response = httpx.get(
            PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
            follow_redirects=True,
        )
        if response.status_code != 200:
            raise RuntimeError(f"NYCU profile fetch failed: {response.status_code} {response.text}")
        payload = response.json()
        username = (payload.get("username") or "").strip()
        email = (payload.get("email") or "").strip()
        if not username:
            raise RuntimeError("NYCU profile missing username")
        if not email:
            email = f"{username}@nycu.edu.tw"
        return NycuOAuthProfile(username=username, email=email)
