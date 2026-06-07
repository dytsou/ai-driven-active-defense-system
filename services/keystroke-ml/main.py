from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from inference import LivenessDetector

app = FastAPI(title="Keystroke ML Risk Service")
DETECTOR = LivenessDetector.load(Path(__file__).parent / "liveness_detector.joblib")
N_FEATURES = len(DETECTOR.feature_columns)


class KeystrokeTiming(BaseModel):
    # raw per-key timestamps in ms (performance.now()); service derives features
    key_down: list[float] = Field(default_factory=list)
    key_up: list[float] = Field(default_factory=list)
    dwell_times: list[float] = Field(default_factory=list)
    flight_times: list[float] = Field(default_factory=list)


class KeystrokePayload(BaseModel):
    present: bool = False
    timing: KeystrokeTiming | None = None
    features: list[float] | None = None  # 16 aggregate features; see docs/keystroke-features.md


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
    model_version: str = "keystroke-ml-v2-liveness"


def _reasons_for(prob: float) -> list[str]:
    if prob >= 0.5:
        return [f"keystroke_synthetic_detected:{prob:.2f}"]
    return ["normal_keystroke"]


def _rate_risk(rate: RateSignals) -> tuple[float, list[str]]:
    risk, reasons = 0.0, []
    if rate.failures_last_5m >= 5:
        risk = max(risk, 0.70); reasons.append("high_failure_rate")
    if rate.distinct_usernames >= 3:
        risk = max(risk, 0.80); reasons.append("credential_stuffing_pattern")
    if rate.login_rate_per_min >= 20:
        risk = max(risk, 0.75); reasons.append("high_login_rate")
    return risk, reasons


@app.get("/health")
def health():
    return {"status": "ok", "model_version": "keystroke-ml-v2-liveness",
            "n_features": N_FEATURES}


@app.post("/v1/risk/score", response_model=RiskScoreResponse)
def score_risk(body: RiskScoreRequest) -> RiskScoreResponse:
    keystroke = body.keystroke or KeystrokePayload()
    baseline = body.baseline or BaselinePayload()
    rate = body.rate_signals or RateSignals()
    reasons: list[str] = []

    prob = None
    if keystroke.features is not None and len(keystroke.features) == N_FEATURES:
        prob = DETECTOR.score_features(keystroke.features)
    elif keystroke.present and keystroke.timing is not None:
        prob = DETECTOR.score_timing(
            keystroke.timing.key_down, keystroke.timing.key_up)

    if not keystroke.present:
        score = 0.85
        reasons.append("missing_keystroke")
    elif prob is not None:
        score = prob
        reasons.extend(_reasons_for(prob))
    elif baseline.exists and baseline.deviation_score >= 0.35:
        score = 0.75
        reasons.append("baseline_deviation")
    else:
        # keystroke present but too short / unusable to featurize
        score = 0.85
        reasons.append("insufficient_keystroke")

    rate_score, rate_reasons = _rate_risk(rate)
    score = max(score, rate_score)
    reasons.extend(rate_reasons)

    if score >= 0.9:
        level, action = "critical", "block"
    elif score >= 0.7:
        level, action = "high", "step_up_mfa"
    elif score >= 0.4:
        level, action = "medium", "allow"
    else:
        level, action = "low", "allow"

    return RiskScoreResponse(risk_score=round(score, 3), risk_level=level,
                             recommended_action=action,
                             reasons=reasons or ["baseline_assessment"])
