from app.services.line_messaging import LineMessagingService


class LineClient:
    """Backward-compatible wrapper around LINE Messaging API push delivery."""

    def send_otp(self, line_user_id: str, otp: str) -> bool:
        return LineMessagingService().send_login_otp(line_user_id, otp)
