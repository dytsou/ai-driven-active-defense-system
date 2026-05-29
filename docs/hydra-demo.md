# Hydra Demo — Active Defense

## Prerequisites

- Docker Compose stack running (`docker compose up -d`)
- Optional: [Hydra](https://github.com/vanhauser-thc/thc-hydra) installed for native HTTP form attacks

## Act 1: Attack simulation

### Option A — bundled script (curl loop)

```bash
chmod +x scripts/demo_hydra.sh
./scripts/demo_hydra.sh
```

This sends rapid `POST /api/v1/auth/login` requests **without keystroke data** from a fixed IP (`203.0.113.99`), mimicking credential stuffing / Hydra traffic.

### Option B — Hydra HTTP form

```bash
hydra -l demo1 -P passwords.txt -s 8000 -V 127.0.0.1 http-post-form \
  "/api/v1/auth/login:username=^USER^&password=^PASS^:invalid"
```

For JSON APIs, prefer the curl loop above or:

```bash
hydra -l demo1 -P passwords.txt -s 8000 127.0.0.1 http-post-json \
  "/api/v1/auth/login:{\"username\":\"^USER^\",\"password\":\"^PASS^\"}:invalid"
```

## What to observe

1. Open **http://localhost:8025** (Mailhog) after MFA triggers.
2. Open **http://localhost:8000/admin/events** as `admin` / `Admin123!` (with normal keystroke timing in the UI).
3. Confirm audit events show elevated `risk_score`, `missing_keystroke`, and `step_up_mfa` / `block` actions.

## Act 2: Behavioral deviation

1. Log in via **http://localhost:8000/** as `demo1` with normal typing.
2. Log in again with artificially slow key timing (or POST anomalous `dwell_times` via API).
3. Expect `mfa_required` even with the correct password.
