# AI Active Defense Login System

Dockerized FastAPI demo: keystroke-aware authentication, ML + rules risk scoring, adaptive MFA, and admin threat monitoring.

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
```

- App: http://localhost:8000
- Mailhog: http://localhost:8025
- Mock ML health: http://localhost:8081/health

### Seed accounts

| User  | Password  | Role                       |
| ----- | --------- | -------------------------- |
| admin | Admin123! | admin                      |
| demo1 | Demo123!  | user (pre-seeded baseline) |
| demo2 | Demo123!  | user                       |

## Development (uv)

```bash
uv sync --extra dev
uv run pytest tests/ -v
uv run uvicorn app.main:app --reload
```

## Demo scripts

- `./scripts/demo_hydra.sh` — external attack simulation (see `docs/hydra-demo.md`)
- `uv run python scripts/seed_db.py` — re-seed database

## Architecture

Modular monolith: **Gateway → Auth → Threat Detection → Response → Data**. ML scoring via `ML_RISK_URL` (mock service included). See `docs/plans/2026-05-29-feat-active-defense-plan.md` for full design.
