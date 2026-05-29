from pydantic import BaseModel, Field


class KeystrokeTiming(BaseModel):
    key_down: list[float] = Field(default_factory=list)
    key_up: list[float] = Field(default_factory=list)
    dwell_times: list[float] = Field(default_factory=list)
    flight_times: list[float] = Field(default_factory=list)


class KeystrokePayload(BaseModel):
    present: bool = False
    timing: KeystrokeTiming | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    keystroke: KeystrokePayload | None = None


class RiskBreakdown(BaseModel):
    ml_score: float | None = None
    rules_score: float | None = None
    behavior_deviation: float | None = None
    ml_source: str | None = None


class LoginResponse(BaseModel):
    status: str
    message: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    action: str | None = None
    mfa_required: bool = False
    mfa_method: str | None = None
    challenge_id: str | None = None
    breakdown: RiskBreakdown | None = None


class MfaSendRequest(BaseModel):
    challenge_id: str


class MfaVerifyRequest(BaseModel):
    challenge_id: str
    otp: str


class MfaResponse(BaseModel):
    status: str
    message: str | None = None


class MLRiskRequest(BaseModel):
    username: str
    ip_address: str
    keystroke: KeystrokePayload | None = None
    recent_failures: int = 0
    login_rate_per_min: float = 0.0


class MLRiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    factors: list[str] = Field(default_factory=list)
    model_version: str = "mock-v1"
