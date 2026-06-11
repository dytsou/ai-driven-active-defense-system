from pathlib import Path
import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field

from inference import LivenessDetector

# ---------------------------
# Logging 設定
# ---------------------------
logger = logging.getLogger("uvicorn.error")

# ---------------------------
# FastAPI app 與模型
# ---------------------------
app = FastAPI(title="Keystroke ML Risk Service")
DETECTOR = LivenessDetector.load(Path(__file__).parent / "liveness_detector.joblib")
N_FEATURES = len(DETECTOR.feature_columns)

# ---------------------------
# Pydantic Models
# ---------------------------
class KeystrokeTiming(BaseModel):
    key_down: list[float] = Field(default_factory=list)
    key_up: list[float] = Field(default_factory=list)
    dwell_times: list[float] = Field(default_factory=list)
    flight_times: list[float] = Field(default_factory=list)


class KeystrokePayload(BaseModel):
    present: bool = False
    timing: KeystrokeTiming | None = None
    features: list[float] | None = None


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


# ---------------------------
# Helper functions
# ---------------------------
def _reasons_for(prob: float) -> list[str]:
    if prob >= 0.5:
        return [f"keystroke_synthetic_detected:{prob:.2f}"]
    return ["normal_keystroke"]


def _rate_risk(rate: RateSignals) -> tuple[float, list[str]]:
    risk, reasons = 0.0, []
    if rate.failures_last_5m >= 5:
        risk = max(risk, 0.70)
        reasons.append("high_failure_rate")
    if rate.distinct_usernames >= 3:
        risk = max(risk, 0.80)
        reasons.append("credential_stuffing_pattern")
    if rate.login_rate_per_min >= 20:
        risk = max(risk, 0.75)
        reasons.append("high_login_rate")
    return risk, reasons


# ---------------------------
# Health endpoint
# ---------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_version": "keystroke-ml-v2-liveness",
        "n_features": N_FEATURES,
        "debug_logging": True
    }


# ---------------------------
# Risk scoring endpoint
# ---------------------------
@app.post("/v1/risk/score", response_model=RiskScoreResponse)
def score_risk(body: RiskScoreRequest) -> RiskScoreResponse:
    keystroke = body.keystroke or KeystrokePayload()
    baseline = body.baseline or BaselinePayload()
    rate = body.rate_signals or RateSignals()
    reasons: list[str] = []

    timing = keystroke.timing
    logger.info(
        "risk input: username=%s present=%s features_len=%s timing=%s key_down_len=%s key_up_len=%s dwell_len=%s flight_len=%s baseline_exists=%s baseline_deviation=%s",
        body.username,
        keystroke.present,
        len(keystroke.features) if keystroke.features is not None else None,
        timing is not None,
        len(timing.key_down) if timing else None,
        len(timing.key_up) if timing else None,
        len(timing.dwell_times) if timing else None,
        len(timing.flight_times) if timing else None,
        baseline.exists,
        baseline.deviation_score,
    )

    # ---------------------------
    # 模型 scoring
    # ---------------------------
    prob = None
    if keystroke.features is not None and len(keystroke.features) == N_FEATURES:
        prob = DETECTOR.score_features(keystroke.features)
        logger.info("risk model path=features prob=%s n_features=%s", prob, N_FEATURES)
    elif keystroke.present and keystroke.timing is not None:
        prob = DETECTOR.score_timing(
            keystroke.timing.key_down, keystroke.timing.key_up
        )
        logger.info("risk model path=timing prob=%s", prob)
    else:
        logger.info("risk model path=none reason=no_features_or_timing")

    # ---------------------------
    # Fallback scoring
    # ---------------------------
    if not keystroke.present:
        score = 0.85
        reasons.append("missing_keystroke")
        logger.info("risk fallback=missing_keystroke score=%s", score)
    elif prob is not None:
        score = prob
        reasons.extend(_reasons_for(prob))
    elif baseline.exists and baseline.deviation_score >= 0.35:
        score = 0.75
        reasons.append("baseline_deviation")
        logger.info("risk fallback=baseline_deviation score=%s", score)
    else:
        score = 0.85
        reasons.append("insufficient_keystroke")
        logger.info(
            "risk fallback=insufficient_keystroke present=%s prob=%s timing=%s features_len=%s",
            keystroke.present,
            prob,
            keystroke.timing is not None,
            len(keystroke.features) if keystroke.features is not None else None,
        )

    # ---------------------------
    # Rate-based risk
    # ---------------------------
    rate_score, rate_reasons = _rate_risk(rate)
    logger.info(
        "risk rate: rate_score=%s failures_last_5m=%s distinct_usernames=%s login_rate_per_min=%s rate_reasons=%s",
        rate_score,
        rate.failures_last_5m,
        rate.distinct_usernames,
        rate.login_rate_per_min,
        rate_reasons,
    )
    score = max(score, rate_score)
    reasons.extend(rate_reasons)

    # ---------------------------
    # Risk level & action
    # ---------------------------
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
        reasons=reasons or ["baseline_assessment"]
    )