from dataclasses import dataclass
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EmailBackend = Literal["brevo_api", "smtp"]


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    smtp_from: str
    user: str
    password: str
    use_tls: bool
    use_ssl: bool


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://active:active@localhost:5432/active_defense"
    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "noreply@active-defense.local"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    email_backend: EmailBackend = "brevo_api"
    brevo_api_key: str = ""
    ml_risk_url: str = "http://localhost:8081"
    ml_api_key: str = ""
    ml_facet_mode: bool = False
    session_secret: str = "dev-secret"
    seed_admin_password: str = "Admin123!"
    seed_demo1_password: str = "Demo123!"
    seed_demo2_password: str = "Demo123!"
    line_mfa_enabled: bool = False
    line_channel_access_token: str = ""
    line_push_api_url: str = "https://api.line.me/v2/bot/message/push"
    ip_block_ttl_seconds: int = 300
    medium_threshold: float = 0.4
    high_threshold: float = 0.7
    block_threshold: float = 0.9
    baseline_deviation_threshold: float = 0.35
    trust_proxy_headers: bool = False
    rate_limit_login_per_min: int = 30
    rate_limit_mfa_send_per_min: int = 5
    rate_limit_mfa_send_per_user_per_min: int = 3
    rate_limit_mfa_send_per_challenge: int = 3
    rate_limit_mfa_verify_per_min: int = 10
    mfa_otp_ttl_seconds: int = 300
    mfa_max_attempts: int = 3
    app_debug: bool = True
    expose_debug_otp: bool = False
    mfa_auto_send: bool = True
    mfa_always_required: bool = False
    ml_timeout_seconds: float = 10.0
    cookie_secure: bool = False
    base_url: str = "http://localhost:8000"
    nycu_oauth_client_id: str = ""
    nycu_oauth_client_secret: str = ""
    nycu_oauth_http_timeout_seconds: float = 60.0
    line_login_channel_id: str = ""
    line_login_channel_secret: str = ""
    line_login_callback_url: str = ""
    line_official_account_url: str = ""
    registration_session_ttl_seconds: int = 900
    rate_limit_register_per_min: int = 20
    frontend_base_url: str = "http://localhost:8000"


settings = Settings()


def nycu_oauth_enabled() -> bool:
    return bool(settings.nycu_oauth_client_id and settings.nycu_oauth_client_secret)


def line_login_enabled() -> bool:
    return bool(
        settings.line_login_channel_id
        and settings.line_login_channel_secret
        and settings.line_login_callback_url
    )


def effective_smtp_config() -> SmtpConfig:
    if settings.app_debug:
        return SmtpConfig(
            host="mailhog",
            port=1025,
            smtp_from="noreply@active-defense.local",
            user="",
            password="",
            use_tls=False,
            use_ssl=False,
        )
    return SmtpConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        smtp_from=settings.smtp_from,
        user=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        use_ssl=settings.smtp_use_ssl,
    )
