"""Plumbing smoke test for the keystroke liveness risk service.

Verifies our model passes through the teammates' service contract: /health,
POST /v1/risk/score, well-formed RiskScoreResponse, and the rule-based paths
(missing keystroke, rate signals) that do not depend on the ML model.

This intentionally does NOT assert "human -> allow" on a single keystroke
sample: model accuracy/robustness is validated by train_liveness.py metrics,
not here. See docs/keystroke-features.md.
"""
from fastapi.testclient import TestClient

from main import app, N_FEATURES

client = TestClient(app)

VALID_ACTIONS = {"allow", "step_up_mfa", "block"}

# a real full-session 16-feature vector (data/REVIEW/.../HUMAN.csv), full precision
SAMPLE_FEATURES = [116.8205, 121.5743, 93.0, 1.0, 1500.0, 1.0407, 254.0729,
                   192.1190, 189.0, 4.0, 1262.0, 0.7562, 702.0, 174388.0,
                   4.0255, 0.1410]


def call(label, keystroke=None, rate_signals=None):
    body = {"username": "demo1", "ip": "127.0.0.1",
            "keystroke": keystroke, "rate_signals": rate_signals or {}}
    d = client.post("/v1/risk/score", json=body).json()
    print(f"  {label:<22} score={d['risk_score']:.2f}  {d['risk_level']:<8} "
          f"{d['recommended_action']:<12} {d['reasons']}")
    return d


health = client.get("/health").json()
assert health["status"] == "ok", health
assert health["n_features"] == N_FEATURES == 16, health
print(f"health OK ({health['model_version']}, {health['n_features']} features); scenarios:")

# 1) ML path runs and returns a well-formed, in-range response
feat = call("features -> ml path", {"present": True, "features": SAMPLE_FEATURES})
assert 0.0 <= feat["risk_score"] <= 1.0, feat
assert feat["recommended_action"] in VALID_ACTIONS, feat
assert any(r.startswith(("normal_keystroke", "keystroke_synthetic")) for r in feat["reasons"]), feat

# 2) missing keystroke -> challenged (rule-based, model-independent)
missing = call("missing keystroke", {"present": False})
assert missing["recommended_action"] in ("step_up_mfa", "block"), missing

# 3) rate signals escalate regardless of keystroke
stuffing = call("credential stuffing", {"present": False},
                {"distinct_usernames": 5, "failures_last_5m": 9})
assert stuffing["risk_score"] >= 0.8, stuffing

print("\nSMOKE TEST PASSED: contract + rule paths verified end-to-end.")
