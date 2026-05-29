import httpx

from app.core.config import settings
from app.schemas.risk import RiskDecision


class MLClient:
    def __init__(self, base_url: str | None = None, http_client: httpx.Client | None = None):
        self.base_url = (base_url or settings.ml_risk_url).rstrip("/")
        self._http = http_client

    def score(
        self,
        *,
        attempt_id: str,
        username: str,
        ip_address: str,
        keystroke_present: bool,
        baseline_exists: bool = False,
        baseline_deviation: float = 0.0,
        signals: dict | None = None,
    ) -> RiskDecision:
        payload = {
            "attempt_id": attempt_id,
            "username": username,
            "ip": ip_address,
            "keystroke": {"present": keystroke_present},
            "baseline": {"exists": baseline_exists, "deviation_score": baseline_deviation},
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
