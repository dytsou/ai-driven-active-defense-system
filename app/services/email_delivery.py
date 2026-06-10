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
    def send_login_code(self, to_email: str, otp: str) -> tuple[bool, str | None]:
        recipient = (to_email or "").strip()
        if not recipient:
            return False, "missing_recipient"

        smtp = effective_smtp_config()
        if self._requires_secure_smtp(smtp) and not (smtp.use_tls or smtp.use_ssl):
            logger.warning(
                "SMTP delivery refused: secure transport required for host=%s",
                smtp.host,
            )
            return False, "tls_required"

        if not smtp.smtp_from.strip():
            logger.warning("SMTP delivery refused: SMTP_FROM is empty")
            return False, "missing_from"

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
                with smtplib.SMTP(smtp.host, smtp.port, timeout=15) as client:
                    if smtp.use_tls:
                        client.starttls()
                    self._authenticate(client, smtp)
                    client.send_message(message)
            return True, None

        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("SMTP failed due to Render firewall block. Shifting to Brevo Web API v3 HTTPS fallback...")
            
            # 💡 終極大絕招：當 SMTP 被 Render 掐死，我們用非同步 httpx 走 443 埠偷渡
            import httpx
            try:
                api_url = "https://api.brevo.com/v3/smtp/email"
                payload = {
                    "sender": {"email": smtp.smtp_from},
                    "to": [{"email": recipient}],
                    "subject": "Your Active Defense login code",
                    "textContent": f"Your verification code is: {otp}"
                }
                headers = {
                    "accept": "application/json",
                    "api-key": smtp.password,  # 你的 xsmtpsib-... 密碼直接當 API Key 用！
                    "content-type": "application/json"
                }
                
                # 使用同步或非同步方式發送（視你這支 func 是不是 async，這裡用標準同步 client 最安全）
                with httpx.Client(timeout=10.0) as http_client:
                    res = http_client.post(api_url, json=payload, headers=headers)
                
                if res.status_code in [200, 201, 202]:
                    logger.info("MFA email successfully sent via Brevo HTTPS API! Anti-firewall win!")
                    return True, None
                else:
                    logger.error(f"Brevo API refused delivery: {res.text}")
                    return False, "api_error"
                    
            except Exception as api_exc:
                logger.error(f"Brevo Web API fallback also failed: {api_exc}")
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
