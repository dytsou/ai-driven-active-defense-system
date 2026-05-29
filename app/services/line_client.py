import httpx

from app.core.config import settings


class LineClient:
    def send_otp(self, line_user_id: str, otp: str) -> bool:
        if not settings.line_mfa_enabled or not settings.line_channel_access_token:
            return False

        response = httpx.post(
            settings.line_push_api_url,
            headers={
                "Authorization": f"Bearer {settings.line_channel_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "to": line_user_id,
                "messages": [{"type": "text", "text": f"Active Defense login code: {otp}"}],
            },
            timeout=10.0,
        )
        return response.status_code == 200
