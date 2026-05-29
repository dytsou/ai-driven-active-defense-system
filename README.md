# AI Active Defense Login System

Dockerized FastAPI demo: keystroke-aware authentication, ML + rules risk scoring, adaptive MFA, and admin threat monitoring.

## Quick start

```bash
cp .env.example .env
COMPOSE_BAKE=true docker compose up -d --build
```

- App: http://localhost:8000
- Mailhog: http://localhost:8025
- Mock ML health: http://localhost:8081/health

## Docker Bake

Custom images (`app`, `mock-ml`) are defined in [`docker-bake.hcl`](docker-bake.hcl). Compose uses the same definitions when `COMPOSE_BAKE=true`.

| Target    | Context               | Image tag                       |
| --------- | --------------------- | ------------------------------- |
| `app`     | `.` (root Dockerfile) | `active-defense/app:latest`     |
| `mock-ml` | `services/mock-ml`    | `active-defense/mock-ml:latest` |

### Build images

```bash
# All targets (default group)
docker buildx bake

# Single target
docker buildx bake app
docker buildx bake mock-ml

# Preview resolved build config
docker buildx bake --print
```

### Run with Compose

```bash
# Build via Bake, then start the stack
COMPOSE_BAKE=true docker compose build
COMPOSE_BAKE=true docker compose up -d

# One-shot build + start
COMPOSE_BAKE=true docker compose up -d --build
```

Set `COMPOSE_BAKE=true` in your shell profile if you always want Bake-backed builds:

```bash
export COMPOSE_BAKE=true
docker compose up -d --build
```

### Tags and registry

Bake variables (defaults shown):

| Variable   | Default   | Purpose                              |
| ---------- | --------- | ------------------------------------ |
| `TAG`      | `latest`  | Image tag suffix                     |
| `REGISTRY` | _(empty)_ | Registry prefix; omit for local tags |

```bash
# Local tags: active-defense/app:v1, active-defense/mock-ml:v1
TAG=v1 docker buildx bake

# Registry tags: ghcr.io/you/active-defense-app:v1, ...
TAG=v1 REGISTRY=ghcr.io/you docker buildx bake --push
```

Postgres, Redis, and Mailhog use upstream images from `docker-compose.yml` only; they are not built by Bake.

### Seed accounts

| User  | Password  | Role                       |
| ----- | --------- | -------------------------- |
| admin | Admin123! | admin                      |
| demo1 | Demo123!  | user (pre-seeded baseline) |
| demo2 | Demo123!  | user                       |

## Development (uv)

```bash
uv sync --extra dev
cd frontend && pnpm install && pnpm run build && cd ..
uv run pytest tests/ -v
uv run uvicorn app.main:app --reload
```

### Frontend (React)

The web UI lives in `frontend/` (Vite + React). It builds into `app/static/dist/` and is served by FastAPI.

```bash
cd frontend
pnpm install
pnpm run dev    # http://localhost:5173 (proxies API to :8000)
pnpm run build  # production bundle for FastAPI / Docker
```

## Demo scripts

- `./scripts/demo_hydra.sh` — external attack simulation (see `docs/hydra-demo.md`)
- `uv run python scripts/seed_db.py` — re-seed database

## Architecture

Modular monolith: **Gateway → Auth → Threat Detection → Response → Data**. ML scoring via `ML_RISK_URL` (mock service included). See `docs/plans/2026-05-29-feat-active-defense-plan.md` for full design.
