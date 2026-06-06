import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

# Public SMTP relays that must not be used without TLS/SSL.
SECURE_SMTP_HOSTS = frozenset(
    {
        "smtp-relay.brevo.com",
        "smtp.mailgun.org",
    }
)


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return email
    if len(local) >= 9:
        return f"{local[:3]}***{local[-3:]}@{domain}"
    if len(local) <= 1:
        return email
    return f"{local[0]}***{local[-1]}@{domain}"


class EmailDeliveryService:
    def send_login_code(self, to_email: str, otp: str) -> bool:
        recipient = (to_email or "").strip()
        if not recipient:
            return False

        if self._requires_secure_smtp() and not (settings.smtp_use_tls or settings.smtp_use_ssl):
            logger.warning(
                "SMTP delivery refused: secure transport required for host=%s",
                settings.smtp_host,
            )
            return False

        message = EmailMessage()
        message["Subject"] = "Your Active Defense login code"
        message["From"] = settings.smtp_from
        message["To"] = recipient
        message.set_content(f"Your verification code is: {otp}")

        try:
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
                    self._authenticate(smtp)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                    if settings.smtp_use_tls:
                        smtp.starttls()
                    self._authenticate(smtp)
                    smtp.send_message(message)
            return True
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning(
                "SMTP delivery failed host=%s port=%s to=%s error=%s",
                settings.smtp_host,
                settings.smtp_port,
                mask_email(recipient),
                exc.__class__.__name__,
            )
            return False

    def _requires_secure_smtp(self) -> bool:
        host = settings.smtp_host.strip().lower()
        if host in SECURE_SMTP_HOSTS:
            return True
        return bool(settings.smtp_user and settings.smtp_password)

    def _authenticate(self, smtp: smtplib.SMTP) -> None:
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
