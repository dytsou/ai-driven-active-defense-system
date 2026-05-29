from pydantic import BaseModel, Field


class RiskSignals(BaseModel):
    failures_last_5m: int = 0
    distinct_usernames: int = 0
    login_rate_per_min: float = 0.0


class RiskDecision(BaseModel):
    risk_score: float
    risk_level: str
    recommended_action: str
    reasons: list[str] = Field(default_factory=list)
    scorer: str
    ml_score: float | None = None
    rules_score: float | None = None
