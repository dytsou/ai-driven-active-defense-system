from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock ML Risk Service")


class KeystrokeTiming(BaseModel):
    dwell_mean: float | None = None
    flight_mean: float | None = None
    hesitation_count: int = 0


class KeystrokePayload(BaseModel):
    present: bool = False
    timing: KeystrokeTiming | None = None


class BaselinePayload(BaseModel):
    exists: bool = False
    deviation_score: float = 0.0


class RateSignals(BaseModel):
    failures_last_5m: int = 0
    distinct_usernames: int = 0
    login_rate_per_min: float = 0.0


class RiskScoreRequest(BaseModel):
    attempt_id: str | None = None
    username: str
    ip: str
    user_agent: str | None = None
    keystroke: KeystrokePayload | None = None
    baseline: BaselinePayload | None = None
    rate_signals: RateSignals | None = None


class RiskScoreResponse(BaseModel):
    risk_score: float
    risk_level: str
    recommended_action: str
    reasons: list[str] = Field(default_factory=list)
    model_version: str = "mock-v1"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/risk/score", response_model=RiskScoreResponse)
def score_risk(body: RiskScoreRequest) -> RiskScoreResponse:
    keystroke = body.keystroke or KeystrokePayload()
    rate = body.rate_signals or RateSignals()
    baseline = body.baseline or BaselinePayload()

    reasons: list[str] = []
    score = 0.15

    if not keystroke.present:
        score = 0.85
        reasons.append("missing_keystroke")
    elif baseline.exists and baseline.deviation_score >= 0.35:
        score = max(score, 0.75)
        reasons.append("baseline_deviation")

    if rate.failures_last_5m >= 5:
        score = max(score, 0.7)
        reasons.append("high_failure_rate")
    if rate.distinct_usernames >= 3:
        score = max(score, 0.8)
        reasons.append("credential_stuffing_pattern")
    if rate.login_rate_per_min >= 20:
        score = max(score, 0.75)
        reasons.append("high_login_rate")

    if keystroke.present and score <= 0.3:
        score = min(score, 0.25)
        reasons.append("normal_keystroke")

    if score >= 0.9:
        level, action = "critical", "block"
    elif score >= 0.7:
        level, action = "high", "step_up_mfa"
    elif score >= 0.4:
        level, action = "medium", "allow"
    else:
        level, action = "low", "allow"

    return RiskScoreResponse(
        risk_score=round(score, 3),
        risk_level=level,
        recommended_action=action,
        reasons=reasons or ["baseline_assessment"],
    )
