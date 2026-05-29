from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://active:active@localhost:5432/active_defense"
    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "noreply@active-defense.local"
    ml_risk_url: str = "http://localhost:8081"
    ml_api_key: str = ""
    ml_facet_mode: bool = False
    session_secret: str = "dev-secret"
    seed_admin_password: str = "Admin123!"
    seed_demo1_password: str = "Demo123!"
    seed_demo2_password: str = "Demo123!"
    line_mfa_enabled: bool = False
    ip_block_ttl_seconds: int = 300
    medium_threshold: float = 0.4
    high_threshold: float = 0.7
    block_threshold: float = 0.9
    baseline_deviation_threshold: float = 0.35
    rate_limit_login_per_min: int = 30
    mfa_otp_ttl_seconds: int = 300
    mfa_max_attempts: int = 3
    ml_timeout_seconds: float = 10.0


settings = Settings()
