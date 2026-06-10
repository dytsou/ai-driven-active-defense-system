from app.core.config import settings
from app.schemas.auth import KeystrokePayload
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
        keystroke: KeystrokePayload | None = None,
        signals: RiskSignals | None = None,
        baseline_exists: bool = False,
        baseline_deviation: float = 0.0,
    ) -> RiskDecision:
        ks = keystroke if keystroke is not None else KeystrokePayload(present=keystroke_present)
        if settings.only_model:
            return self._analyze_model_only(
                username=username,
                ip_address=ip_address,
                attempt_id=attempt_id,
                keystroke=ks,
                baseline_exists=baseline_exists,
                baseline_deviation=baseline_deviation,
            )

        signals = signals or RiskSignals()
        rules = self.rules_engine.evaluate(
            RulesContext(
                keystroke_present=ks.present,
                signals=signals,
                baseline_deviation=baseline_deviation,
            )
        )

        try:
            ml = self.ml_client.score(
                attempt_id=attempt_id,
                username=username,
                ip_address=ip_address,
                keystroke=ks,
                baseline_exists=baseline_exists,
                baseline_deviation=baseline_deviation,
                signals=signals.model_dump(),
            )
            return self.orchestrator.merge(ml, rules)
        except Exception:
            # Dual-gate fail-closed: never allow on rules alone when ML is unavailable.
            # Default to step_up_mfa; rules may still escalate to block.
            ml_unavailable = RiskDecision(
                risk_score=0.75,
                risk_level="high",
                recommended_action="step_up_mfa",
                reasons=["ml_unavailable"],
                scorer="ml_unavailable",
                ml_score=0.75,
            )
            return self.orchestrator.merge(ml_unavailable, rules)

    def _analyze_model_only(
        self,
        *,
        username: str,
        ip_address: str,
        attempt_id: str,
        keystroke: KeystrokePayload,
        baseline_exists: bool,
        baseline_deviation: float,
    ) -> RiskDecision:
        try:
            return self.ml_client.score(
                attempt_id=attempt_id,
                username=username,
                ip_address=ip_address,
                keystroke=keystroke,
                keystroke_present=keystroke.present,
                baseline_exists=baseline_exists,
                baseline_deviation=baseline_deviation,
                signals=RiskSignals().model_dump(),
            )
        except Exception:
            return RiskDecision(
                risk_score=0.2,
                risk_level="low",
                recommended_action="allow",
                reasons=["ml_unavailable"],
                scorer="ml_unavailable",
                ml_score=0.2,
            )
