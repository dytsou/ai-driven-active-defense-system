# ML Risk API v1

## Aggregate endpoint

`POST /v1/risk/score`

### Request

```json
{
  "attempt_id": "uuid",
  "username": "demo1",
  "ip": "127.0.0.1",
  "keystroke": { "present": true },
  "baseline": { "exists": true, "deviation_score": 0.1 },
  "rate_signals": {
    "failures_last_5m": 0,
    "distinct_usernames": 0,
    "login_rate_per_min": 1.0
  }
}
```

### Response

```json
{
  "risk_score": 0.25,
  "risk_level": "low",
  "recommended_action": "allow",
  "reasons": ["normal_keystroke"],
  "model_version": "mock-v1"
}
```

### Mock contract

- `keystroke.present=false` → `risk_score >= 0.8`, action at least `step_up_mfa`
- Normal keystroke + low rate signals → `risk_score <= 0.3`, `allow`
- ML timeout/error → application uses `rules_fallback` scorer only
