import logging
import smtplib
from email.message import EmailMessage

from app.core.config import SmtpConfig, effective_smtp_config, settings

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

        smtp = effective_smtp_config()
        if self._requires_secure_smtp(smtp) and not (smtp.use_tls or smtp.use_ssl):
            logger.warning(
                "SMTP delivery refused: secure transport required for host=%s",
                smtp.host,
            )
            return False

        message = EmailMessage()
        message["Subject"] = "Your Active Defense login code"
        message["From"] = smtp.smtp_from
        message["To"] = recipient
        message.set_content(f"Your verification code is: {otp}")

        try:
            if smtp.use_ssl:
                with smtplib.SMTP_SSL(smtp.host, smtp.port) as client:
                    self._authenticate(client, smtp)
                    client.send_message(message)
            else:
                with smtplib.SMTP(smtp.host, smtp.port) as client:
                    if smtp.use_tls:
                        client.starttls()
                    self._authenticate(client, smtp)
                    client.send_message(message)
            if settings.app_debug:
                logger.info(
                    "MFA email sent via debug SMTP host=%s to=%s (view Mailhog at :8025)",
                    smtp.host,
                    mask_email(recipient),
                )
            return True
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning(
                "SMTP delivery failed host=%s port=%s to=%s error=%s",
                smtp.host,
                smtp.port,
                mask_email(recipient),
                exc.__class__.__name__,
            )
            return False

    @staticmethod
    def _requires_secure_smtp(smtp: SmtpConfig) -> bool:
        host = smtp.host.strip().lower()
        if host in SECURE_SMTP_HOSTS:
            return True
        return bool(smtp.user and smtp.password)

    @staticmethod
    def _authenticate(client: smtplib.SMTP, smtp: SmtpConfig) -> None:
        if smtp.user and smtp.password:
            client.login(smtp.user, smtp.password)
