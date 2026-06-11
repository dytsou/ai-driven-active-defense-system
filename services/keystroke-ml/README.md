# keystroke-ml service

Drop-in replacement for the legacy `services/mock-ml` rules stub: same `POST /v1/risk/score` contract
on port 8081, so the app uses it by pointing `ML_RISK_URL` at it. It scores
keystroke **liveness** (real human vs machine-synthesized typing) from the raw
key timing of whatever the user types — free text, no fixed password. Without
usable timing it falls back to the same present/rate/deviation rules the mock used.

Feature/format spec for the frontend: see `docs/keystroke-features.md`.

## Model artifact

`liveness_detector.joblib` is **not committed** (regenerable). Generate it from
the dataset under `data/` before running or building. Current config
(HistGradientBoosting, mixed-length login windows, 24 features, length-agnostic —
see `docs/keystroke-experiments.md`):

```
python train_liveness.py --corpora GAY,GUN,REVIEW,LSIA \
  --window mixed --max-windows 6 --extra-features \
  --min-keys 10 --save-only HistGradientBoosting
```

`scikit-learn` is pinned in `requirements.txt`; a different version may fail to
load the model file.

## Run

```
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8081
python smoke_test.py
```

## Input the model needs

Send raw per-key timestamps (ms, from `performance.now()`); the service derives
the 24 aggregate features itself:

```json
{
  "username": "demo1",
  "ip": "127.0.0.1",
  "keystroke": {
    "present": true,
    "timing": {
      "key_down": [
        /* ms */
      ],
      "key_up": [
        /* ms */
      ]
    }
  },
  "rate_signals": {}
}
```

Alternatively send `keystroke.features` as the 24 floats listed in
`docs/keystroke-features.md` (same order). If neither a usable `timing` nor a
length-24 `features` is present, the service uses the fallback rules.

## Output

```json
{
  "risk_score": 0.93,
  "risk_level": "critical",
  "recommended_action": "block",
  "reasons": ["keystroke_synthetic_detected:0.93"],
  "model_version": "keystroke-ml-v2-liveness"
}
```

`recommended_action` is `allow` / `step_up_mfa` / `block`.

> Notes: the model is trained on mixed-length login windows (12–40 keys), so it
> is length-agnostic; inputs below `min_keys` (default 10) are not scored and
> fall back to MFA/rate rules. Single-login accuracy is lower than the aggregate
> AUC — keystroke liveness is a supplementary risk signal, never the sole gate.
> See `docs/keystroke-experiments.md`.
