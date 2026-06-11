import logging

import httpx

from app.core.config import settings
from app.schemas.auth import KeystrokePayload
from app.schemas.risk import RiskDecision
from app.services.behavior_service import BehaviorService

logger = logging.getLogger(__name__)


class MLClient:
    def __init__(
        self,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        behavior: BehaviorService | None = None,
    ):
        self.base_url = (base_url or settings.ml_risk_url).rstrip("/")
        self._http = http_client
        self._behavior = behavior or BehaviorService()

    def score(
        self,
        *,
        attempt_id: str,
        username: str,
        ip_address: str,
        keystroke: KeystrokePayload | None = None,
        keystroke_present: bool | None = None,
        baseline_exists: bool = False,
        baseline_deviation: float = 0.0,
        signals: dict | None = None,
    ) -> RiskDecision:
        ks = keystroke or KeystrokePayload()

        if keystroke_present is not None:
            ks = ks.model_copy(update={"present": keystroke_present})

        keystroke_body: dict = {"present": ks.present}

        if ks.features is not None:
            keystroke_body["features"] = ks.features

        elif ks.present and ks.timing is not None:
            # Forward raw timing; ML service derives the 24 features itself.
            keystroke_body["timing"] = {
                "key_down": ks.timing.key_down,
                "key_up": ks.timing.key_up,
                "dwell_times": ks.timing.dwell_times,
                "flight_times": ks.timing.flight_times,
            }

        logger.info(
            "ml_client payload: username=%s present=%s features_len=%s timing=%s key_down_len=%s key_up_len=%s dwell_len=%s flight_len=%s",
            username,
            ks.present,
            len(ks.features) if ks.features is not None else None,
            ks.timing is not None,
            len(ks.timing.key_down) if ks.timing else None,
            len(ks.timing.key_up) if ks.timing else None,
            len(ks.timing.dwell_times) if ks.timing else None,
            len(ks.timing.flight_times) if ks.timing else None,
        )

        payload = {
            "attempt_id": attempt_id,
            "username": username,
            "ip": ip_address,
            "keystroke": keystroke_body,
            "baseline": {
                "exists": baseline_exists,
                "deviation_score": baseline_deviation,
            },
            "rate_signals": signals or {},
        }

        client = self._http
        owns = client is None

        if owns:
            client = httpx.Client(timeout=settings.ml_timeout_seconds)

        try:
            response = client.post(f"{self.base_url}/v1/risk/score", json=payload)
            response.raise_for_status()
            data = response.json()

            return RiskDecision(
                risk_score=data["risk_score"],
                risk_level=data["risk_level"],
                recommended_action=data["recommended_action"],
                reasons=data.get("reasons", []),
                scorer="ml_aggregate",
                ml_score=data["risk_score"],
            )
        finally:
            if owns:
                client.close()