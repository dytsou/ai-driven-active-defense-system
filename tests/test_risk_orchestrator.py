import pytest

from app.schemas.risk import RiskDecision, RiskSignals
from app.services.risk_orchestrator import RiskOrchestrator


def test_merge_takes_stricter_action():
    orchestrator = RiskOrchestrator()
    ml = RiskDecision(risk_score=0.5, risk_level="medium", recommended_action="allow", reasons=[], scorer="ml")
    rules = RiskDecision(
        risk_score=0.85, risk_level="high", recommended_action="step_up_mfa", reasons=["missing_keystroke"], scorer="rules"
    )
    merged = orchestrator.merge(ml, rules)
    assert merged.recommended_action == "step_up_mfa"
    assert merged.risk_score == 0.85


def test_block_beats_mfa():
    orchestrator = RiskOrchestrator()
    ml = RiskDecision(risk_score=0.95, risk_level="critical", recommended_action="block", reasons=[], scorer="ml")
    rules = RiskDecision(risk_score=0.8, risk_level="high", recommended_action="step_up_mfa", reasons=[], scorer="rules")
    merged = orchestrator.merge(ml, rules)
    assert merged.recommended_action == "block"


def test_ml_failure_uses_rules_fallback():
    from app.services.threat_analyzer import ThreatAnalyzer

    analyzer = ThreatAnalyzer(ml_client=_FailingMLClient(), rules_engine=_HighRiskRules())
    decision = analyzer.analyze(
        username="demo1",
        ip_address="10.0.0.1",
        keystroke_present=False,
        signals=RiskSignals(failures_last_5m=10, login_rate_per_min=30),
    )
    assert decision.scorer == "rules_fallback"
    assert decision.recommended_action in ("step_up_mfa", "block")


def test_missing_keystroke_triggers_mfa_via_ml(mock_ml_client):
    from app.services.threat_analyzer import ThreatAnalyzer
    from app.services.rules_engine import RulesEngine

    analyzer = ThreatAnalyzer(ml_client=mock_ml_client, rules_engine=RulesEngine())
    decision = analyzer.analyze(
        username="demo1",
        ip_address="10.0.0.1",
        keystroke_present=False,
        signals=RiskSignals(),
    )
    assert decision.recommended_action in ("step_up_mfa", "block")
    assert decision.risk_score >= 0.7
    assert "missing_keystroke" in decision.reasons


def test_normal_keystroke_low_rate_allows(mock_ml_client):
    from app.services.threat_analyzer import ThreatAnalyzer
    from app.services.rules_engine import RulesEngine

    analyzer = ThreatAnalyzer(ml_client=mock_ml_client, rules_engine=RulesEngine())
    decision = analyzer.analyze(
        username="demo1",
        ip_address="10.0.0.1",
        keystroke_present=True,
        signals=RiskSignals(failures_last_5m=0, login_rate_per_min=1),
        baseline_deviation=0.05,
    )
    assert decision.recommended_action == "allow"
    assert decision.risk_score <= 0.4


class _FailingMLClient:
    def score(self, **_kwargs):
        raise ConnectionError("ml unavailable")


class _HighRiskRules:
    def evaluate(self, _context):
        return RiskDecision(
            risk_score=0.9,
            risk_level="critical",
            recommended_action="block",
            reasons=["rules_only"],
            scorer="rules",
        )
