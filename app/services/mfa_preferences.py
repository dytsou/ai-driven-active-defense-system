from app.db.models import User


def mfa_delivery_channels(user: User) -> list[str]:
    channels: list[str] = []
    if user.email:
        channels.append("email")
    if user.line_user_id and user.mfa_line_enabled:
        channels.append("line")
    return channels


def mfa_channels_label(user: User) -> str:
    channels = mfa_delivery_channels(user)
    if channels == ["email", "line"]:
        return "both"
    if channels == ["line"]:
        return "line"
    return "email"
