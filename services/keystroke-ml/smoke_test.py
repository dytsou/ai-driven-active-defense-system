"""Plumbing smoke test for the keystroke liveness risk service.

Verifies our model passes through the teammates' service contract end-to-end:
/health, POST /v1/risk/score, well-formed RiskScoreResponse, the raw-timing ML
path (24 features derived in-service), and the model-independent rule paths.

It does NOT assert "human -> allow" on a single sample: single-login accuracy is
weaker than the aggregate AUC (see docs/keystroke-experiments.md). Model quality
is tracked by train_liveness.py metrics, not here.
"""
from fastapi.testclient import TestClient

from main import app, N_FEATURES

client = TestClient(app)

VALID_ACTIONS = {"allow", "step_up_mfa", "block"}

# a real 25-key human window (data/REVIEW/.../HUMAN.csv), key_down/key_up in ms
KEY_DOWN = [0.0, 371.0, 628.0, 736.0, 1015.0, 1105.0, 1323.0, 1536.0, 1828.0,
            2168.0, 2466.0, 2967.0, 3724.0, 3944.0, 4203.0, 4439.0, 4818.0,
            5651.0, 5766.0, 5920.0, 6101.0, 6298.0, 6475.0, 6600.0, 6734.0]
KEY_UP = [69.0, 484.0, 690.0, 860.0, 1091.0, 1195.0, 1408.0, 1654.0, 2320.0,
          2310.0, 2580.0, 3271.0, 3842.0, 4066.0, 4294.0, 4564.0, 4939.0,
          5726.0, 5871.0, 5987.0, 6197.0, 6374.0, 6561.0, 6802.0, 6883.0]


def call(label, keystroke=None, rate_signals=None):
    body = {"username": "demo1", "ip": "127.0.0.1",
            "keystroke": keystroke, "rate_signals": rate_signals or {}}
    d = client.post("/v1/risk/score", json=body).json()
    print(f"  {label:<22} score={d['risk_score']:.2f}  {d['risk_level']:<8} "
          f"{d['recommended_action']:<12} {d['reasons']}")
    return d


health = client.get("/health").json()
assert health["status"] == "ok", health
assert health["n_features"] == N_FEATURES == 24, health
print(f"health OK ({health['model_version']}, {health['n_features']} features); scenarios:")

# 1) raw-timing ML path runs end-to-end and returns a well-formed, in-range result
timing = call("raw timing -> ml", {"present": True,
              "timing": {"key_down": KEY_DOWN, "key_up": KEY_UP}})
assert 0.0 <= timing["risk_score"] <= 1.0, timing
assert timing["recommended_action"] in VALID_ACTIONS, timing
assert any(r.startswith(("normal_keystroke", "keystroke_synthetic")) for r in timing["reasons"]), timing

# 2) missing keystroke -> challenged (rule-based, model-independent)
missing = call("missing keystroke", {"present": False})
assert missing["recommended_action"] in ("step_up_mfa", "block"), missing

# 3) rate signals escalate regardless of keystroke
stuffing = call("credential stuffing", {"present": False},
                {"distinct_usernames": 5, "failures_last_5m": 9})
assert stuffing["risk_score"] >= 0.8, stuffing

print("\nSMOKE TEST PASSED: contract + raw-timing + rule paths verified end-to-end.")
