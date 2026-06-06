from urllib.parse import urlencode

import httpx

from app.core.config import settings

LINE_AUTH_URL = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"


class LineOAuthError(Exception):
    pass


class LineOAuthService:
    def __init__(
        self,
        channel_id: str | None = None,
        channel_secret: str | None = None,
        redirect_uri: str | None = None,
    ):
        self.channel_id = channel_id or settings.line_login_channel_id
        self.channel_secret = channel_secret or settings.line_login_channel_secret
        self.redirect_uri = redirect_uri or settings.line_login_callback_url

    def authorization_url(self, state: str, nonce: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.channel_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "profile openid",
            "nonce": nonce,
        }
        return f"{LINE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> str:
        response = httpx.post(
            LINE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.channel_id,
                "client_secret": self.channel_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if response.status_code != 200:
            raise LineOAuthError(f"LINE token exchange failed: {response.status_code}")
        payload = response.json()
        id_token = payload.get("id_token")
        if not id_token:
            raise LineOAuthError("LINE token response missing id_token")
        return id_token

    def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> str:
        response = httpx.post(
            LINE_VERIFY_URL,
            data={"id_token": id_token, "client_id": self.channel_id},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if response.status_code != 200:
            raise LineOAuthError("LINE id_token verification failed")
        payload = response.json()
        if payload.get("iss") != "https://access.line.me":
            raise LineOAuthError("Invalid LINE token issuer")
        if payload.get("aud") != self.channel_id:
            raise LineOAuthError("Invalid LINE token audience")
        if nonce and payload.get("nonce") != nonce:
            raise LineOAuthError("Invalid LINE token nonce")
        sub = (payload.get("sub") or "").strip()
        if not sub:
            raise LineOAuthError("LINE token missing sub")
        return sub
