import logging
import httpx
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
    def send_login_code(self, to_email: str, otp: str) -> tuple[bool, str | None]:
        recipient = (to_email or "").strip()
        if not recipient:
            return False, "missing_recipient"

        smtp = effective_smtp_config()
        
        if not smtp.smtp_from.strip():
            logger.warning("Email delivery refused: SMTP_FROM is empty")
            return False, "missing_from"

        if settings.app_debug:
            logger.info("Local / Debug environment detected. Delivering via conventional SMTP...")
            message = EmailMessage()
            message["Subject"] = "Your Active Defense login code"
            message["From"] = smtp.smtp_from
            message["To"] = recipient
            message.set_content(f"Your verification code is: {otp}")

            try:
                with smtplib.SMTP(smtp.host, smtp.port, timeout=5) as client:
                    client.send_message(message)
                logger.info(
                    "MFA email sent via debug SMTP host=%s to=%s (view Mailhog at :8025)",
                    smtp.host,
                    mask_email(recipient),
                )
                return True, None
            except (OSError, smtplib.SMTPException) as exc:
                logger.warning("Local SMTP delivery failed: %s", exc)
                return False, "smtp_error"

        # 🚀 情況二：雲端正式環境 ➡️ 繞過 Render 防火牆，直接使用 Brevo Web API v3
        logger.info("Production environment detected. Rerouting delivery to Brevo Web API v3 (HTTPS)...")
        
        if not smtp.password:
            logger.error("Email delivery refused: smtp_password (API Key) is not configured")
            return False, "smtp_auth_failed"

        api_url = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {"email": smtp.smtp_from},
            "to": [{"email": recipient}],
            "subject": "Your Active Defense login code",
            "textContent": f"Your verification code is: {otp}"
        }
        headers = {
            "accept": "application/json",
            "api-key": smtp.password,  # ➡️ 完美對齊原廠架構，直接抓取 Pydantic Config 中的密碼
            "content-type": "application/json"
        }

        try:
            with httpx.Client(timeout=10.0) as http_client:
                res = http_client.post(api_url, json=payload, headers=headers)
            
            if res.status_code in [200, 201, 202]:
                logger.info("MFA email successfully sent via Brevo HTTPS API! Anti-firewall win!")
                return True, None
            else:
                logger.error("Brevo API refused delivery (Status %d): %s", res.status_code, res.text)
                return False, "api_error"
                
        except Exception as api_exc:
            logger.error("Brevo Web API connection crashed: %s", api_exc)
            return False, "smtp_error"

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
