from app.schemas.risk import RiskDecision, RiskSignals
from app.services.ml_client import MLClient
from app.services.risk_orchestrator import RiskOrchestrator
from app.services.rules_engine import RulesContext, RulesEngine


class ThreatAnalyzer:
    def __init__(
        self,
        ml_client: MLClient | None = None,
        rules_engine: RulesEngine | None = None,
        orchestrator: RiskOrchestrator | None = None,
    ):
        self.ml_client = ml_client or MLClient()
        self.rules_engine = rules_engine or RulesEngine()
        self.orchestrator = orchestrator or RiskOrchestrator()

    def analyze(
        self,
        *,
        username: str,
        ip_address: str,
        attempt_id: str = "test-attempt",
        keystroke_present: bool,
        signals: RiskSignals | None = None,
        baseline_exists: bool = False,
        baseline_deviation: float = 0.0,
    ) -> RiskDecision:
        signals = signals or RiskSignals()
        rules = self.rules_engine.evaluate(
            RulesContext(
                keystroke_present=keystroke_present,
                signals=signals,
                baseline_deviation=baseline_deviation,
            )
        )

        try:
            ml = self.ml_client.score(
                attempt_id=attempt_id,
                username=username,
                ip_address=ip_address,
                keystroke_present=keystroke_present,
                baseline_exists=baseline_exists,
                baseline_deviation=baseline_deviation,
                signals=signals.model_dump(),
            )
            return self.orchestrator.merge(ml, rules)
        except Exception:
            fallback = rules.model_copy(update={"scorer": "rules_fallback"})
            return fallback
