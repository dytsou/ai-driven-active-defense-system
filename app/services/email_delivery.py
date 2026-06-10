import logging
import smtplib
from email.message import EmailMessage

from app.core.config import SmtpConfig, effective_smtp_config, settings
from app.services.brevo_email import send_transactional_email

logger = logging.getLogger(__name__)

LOGIN_CODE_SUBJECT = "Your Active Defense login code"
SECURE_SMTP_HOSTS = frozenset(
    {
        "smtp-relay.brevo.com",
        "smtp.mailgun.org",
    }
)
DEBUG_SMTP_TIMEOUT_SECONDS = 5.0
SMTP_TIMEOUT_SECONDS = 15.0


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
    def send_login_code(self, to_email: str, otp: str) -> tuple[bool, str | None]:
        recipient = (to_email or "").strip()
        if not recipient:
            return False, "missing_recipient"

        smtp = effective_smtp_config()
        if not smtp.smtp_from.strip():
            logger.warning("Email delivery refused: SMTP_FROM is empty")
            return False, "missing_from"

        if settings.app_debug:
            return self._send_via_debug_smtp(smtp, recipient, otp)

        if settings.email_backend == "brevo_api":
            return self._send_via_brevo_api(smtp.smtp_from, recipient, otp)

        return self._send_via_smtp(smtp, recipient, otp)

    def _send_via_debug_smtp(
        self, smtp: SmtpConfig, recipient: str, otp: str
    ) -> tuple[bool, str | None]:
        message = self._build_message(smtp.smtp_from, recipient, otp)
        try:
            with smtplib.SMTP(smtp.host, smtp.port, timeout=DEBUG_SMTP_TIMEOUT_SECONDS) as client:
                client.send_message(message)
            logger.info(
                "MFA email sent via debug SMTP host=%s to=%s (view Mailhog at :8025)",
                smtp.host,
                mask_email(recipient),
            )
            return True, None
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("Local SMTP delivery failed: %s", exc.__class__.__name__)
            return False, "smtp_error"

    def _send_via_brevo_api(
        self, sender: str, recipient: str, otp: str
    ) -> tuple[bool, str | None]:
        api_key = settings.brevo_api_key.strip()
        if not api_key:
            logger.error("Email delivery refused: BREVO_API_KEY is not configured")
            return False, "missing_api_key"

        logger.info("Delivering MFA email via Brevo Web API v3")
        return send_transactional_email(
            api_key=api_key,
            sender=sender,
            recipient=recipient,
            subject=LOGIN_CODE_SUBJECT,
            text_content=f"Your verification code is: {otp}",
        )

    def _send_via_smtp(
        self, smtp: SmtpConfig, recipient: str, otp: str
    ) -> tuple[bool, str | None]:
        if self._requires_secure_smtp(smtp) and not (smtp.use_tls or smtp.use_ssl):
            logger.warning(
                "SMTP delivery refused: secure transport required for host=%s",
                smtp.host,
            )
            return False, "tls_required"

        message = self._build_message(smtp.smtp_from, recipient, otp)
        try:
            if smtp.use_ssl:
                with smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=SMTP_TIMEOUT_SECONDS) as client:
                    self._authenticate(client, smtp)
                    client.send_message(message)
            else:
                with smtplib.SMTP(smtp.host, smtp.port, timeout=SMTP_TIMEOUT_SECONDS) as client:
                    if smtp.use_tls:
                        client.starttls()
                    self._authenticate(client, smtp)
                    client.send_message(message)
            logger.info(
                "MFA email sent via SMTP host=%s to=%s",
                smtp.host,
                mask_email(recipient),
            )
            return True, None
        except smtplib.SMTPAuthenticationError as exc:
            code = getattr(exc, "smtp_code", None)
            logger.warning(
                "SMTP authentication failed host=%s user=%s code=%s",
                smtp.host,
                smtp.user,
                code,
            )
            if code == 525:
                return False, "smtp_ip_blocked"
            return False, "smtp_auth_failed"
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning(
                "SMTP delivery failed host=%s port=%s to=%s error=%s",
                smtp.host,
                smtp.port,
                mask_email(recipient),
                exc.__class__.__name__,
            )
            return False, "smtp_error"

    @staticmethod
    def _build_message(sender: str, recipient: str, otp: str) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = LOGIN_CODE_SUBJECT
        message["From"] = sender
        message["To"] = recipient
        message.set_content(f"Your verification code is: {otp}")
        return message

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
