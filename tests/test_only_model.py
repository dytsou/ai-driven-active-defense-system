from app.core.config import settings
from app.schemas.auth import KeystrokePayload, KeystrokeTiming
from app.schemas.risk import RiskDecision, RiskSignals
from app.services.rules_engine import RulesEngine
from app.services.threat_analyzer import ThreatAnalyzer


NORMAL_KEYSTROKE = KeystrokePayload(
    present=True,
    timing=KeystrokeTiming(
        dwell_times=[95, 92, 98],
        flight_times=[110, 108, 112],
    ),
)


class _RecordingMLClient:
    def __init__(self, decision: RiskDecision):
        self.decision = decision
        self.last_signals: dict | None = None

    def score(self, **kwargs):
        self.last_signals = kwargs.get("signals")
        return self.decision


class _HighRiskRules(RulesEngine):
    def evaluate(self, _context):
        return RiskDecision(
            risk_score=0.95,
            risk_level="critical",
            recommended_action="block",
            reasons=["rules_only"],
            scorer="rules",
            rules_score=0.95,
        )


def test_only_model_ignores_rules_and_ip_signals(monkeypatch):
    monkeypatch.setattr(settings, "only_model", True)
    ml = _RecordingMLClient(
        RiskDecision(
            risk_score=0.2,
            risk_level="low",
            recommended_action="allow",
            reasons=["normal_keystroke"],
            scorer="ml_aggregate",
            ml_score=0.2,
        )
    )
    analyzer = ThreatAnalyzer(ml_client=ml, rules_engine=_HighRiskRules())

    decision = analyzer.analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=True,
        keystroke=NORMAL_KEYSTROKE,
        signals=RiskSignals(failures_last_5m=10, distinct_usernames=5, login_rate_per_min=30),
    )

    assert decision.recommended_action == "allow"
    assert decision.scorer == "ml_aggregate"
    assert ml.last_signals == {
        "failures_last_5m": 0,
        "distinct_usernames": 0,
        "login_rate_per_min": 0.0,
    }


def test_only_model_still_uses_ml_for_missing_keystroke(monkeypatch, mock_ml_client):
    monkeypatch.setattr(settings, "only_model", True)
    analyzer = ThreatAnalyzer(ml_client=mock_ml_client, rules_engine=RulesEngine())

    decision = analyzer.analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=False,
        signals=RiskSignals(failures_last_5m=0),
    )

    assert decision.recommended_action == "step_up_mfa"
    assert "missing_keystroke" in decision.reasons


def test_only_model_ml_unavailable_falls_back_to_allow(monkeypatch):
    monkeypatch.setattr(settings, "only_model", True)

    class _FailingML:
        def score(self, **_kwargs):
            raise ConnectionError("ml down")

    decision = ThreatAnalyzer(ml_client=_FailingML()).analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=False,
        signals=RiskSignals(failures_last_5m=10),
    )

    assert decision.recommended_action == "allow"
    assert decision.scorer == "ml_unavailable"


def test_dual_gate_allow_only_when_both_allow(monkeypatch):
    monkeypatch.setattr(settings, "only_model", False)
    ml = _RecordingMLClient(
        RiskDecision(
            risk_score=0.2,
            risk_level="low",
            recommended_action="allow",
            reasons=["normal_keystroke"],
            scorer="ml_aggregate",
            ml_score=0.2,
        )
    )
    analyzer = ThreatAnalyzer(ml_client=ml, rules_engine=RulesEngine())

    decision = analyzer.analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=True,
        keystroke=NORMAL_KEYSTROKE,
        signals=RiskSignals(failures_last_5m=0, login_rate_per_min=1),
        baseline_deviation=0.05,
    )

    assert decision.recommended_action == "allow"
    assert decision.scorer == "merged"


def test_dual_gate_blocks_ml_allow_when_rules_escalate(monkeypatch):
    monkeypatch.setattr(settings, "only_model", False)
    ml = _RecordingMLClient(
        RiskDecision(
            risk_score=0.2,
            risk_level="low",
            recommended_action="allow",
            reasons=["normal_keystroke"],
            scorer="ml_aggregate",
            ml_score=0.2,
        )
    )
    analyzer = ThreatAnalyzer(ml_client=ml, rules_engine=RulesEngine())

    decision = analyzer.analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=False,
        signals=RiskSignals(failures_last_5m=0),
    )

    assert decision.recommended_action in ("step_up_mfa", "block")
    assert "missing_keystroke" in decision.reasons


def test_dual_gate_ml_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "only_model", False)

    class _FailingML:
        def score(self, **_kwargs):
            raise ConnectionError("ml down")

    decision = ThreatAnalyzer(ml_client=_FailingML(), rules_engine=RulesEngine()).analyze(
        username="demo2",
        ip_address="10.0.0.1",
        keystroke_present=True,
        keystroke=NORMAL_KEYSTROKE,
        signals=RiskSignals(failures_last_5m=0, login_rate_per_min=1),
        baseline_deviation=0.05,
    )

    assert decision.recommended_action == "step_up_mfa"
    assert decision.scorer == "merged"
    assert "ml_unavailable" in decision.reasons


def test_only_model_login_ignores_ip_spray_for_mfa(auth_client, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "only_model", True)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "203.0.113.88"}

    for username in ("nobody", "guest", "root"):
        auth_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong"},
            headers=headers,
        )

    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo2",
            "password": settings.seed_demo2_password,
            "keystroke": {
                "present": True,
                "timing": {
                    "dwell_times": [95, 92, 98],
                    "flight_times": [110, 108, 112],
                },
            },
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
