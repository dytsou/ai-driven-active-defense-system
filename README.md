# AI Active Defense Login System

Dockerized FastAPI demo: keystroke-aware authentication, ML + rules risk scoring, adaptive MFA, and admin threat monitoring.

## Quick start

```bash
cp .env.example .env
make up
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
make bake

# Single target
make bake TARGET=app
make bake TARGET=mock-ml

# Preview resolved build config
make bake-print
```

### Run with Compose

```bash
# Build via Bake, then start the stack
make build
make up

# One-shot build + start
make up
```

### Tags and registry

Bake variables (defaults shown):

| Variable   | Default   | Purpose                              |
| ---------- | --------- | ------------------------------------ |
| `TAG`      | `latest`  | Image tag suffix                     |
| `REGISTRY` | _(empty)_ | Registry prefix; omit for local tags |

```bash
# Local tags: active-defense/app:v1, active-defense/mock-ml:v1
make bake TAG=v1

# Registry tags + push: ghcr.io/you/active-defense-app:v1, ...
make bake TAG=v1 REGISTRY=ghcr.io/you
docker buildx bake --push   # or add --push to the command above
```

Postgres, Redis, and Mailhog use upstream images from `docker-compose.yml` only; they are not built by Bake.

### Seed accounts

| User  | Password  | Role                       |
| ----- | --------- | -------------------------- |
| admin | Admin123! | admin                      |
| demo1 | Demo123!  | user (pre-seeded baseline) |
| demo2 | Demo123!  | user                       |

## Tool versions

Pinned so local dev, CI, and Docker stay aligned:

| Tool   | Version | Pin file                           |
| ------ | ------- | ---------------------------------- |
| Python | 3.12    | `.python-version`                  |
| Node   | 25.9.0  | `frontend/.nvmrc`                  |
| pnpm   | 11.1.3  | `frontend/package.json` (Corepack) |

Use Corepack for pnpm (global `pnpm` 10.x will not match CI):

```bash
corepack enable
cd frontend && pnpm -v   # should print 11.1.3
```

After changing `.python-version`, run `uv python install` then `uv sync --extra dev`.

## Development (uv)

```bash
uv sync --extra dev
cd frontend && corepack enable && pnpm install && pnpm run build && cd ..
uv run pytest tests/ -v
uv run uvicorn app.main:app --reload
```

### Frontend (React)

The web UI lives in `frontend/` (Vite + React). It builds into `app/static/dist/` and is served by FastAPI.

```bash
cd frontend
corepack enable
pnpm install
pnpm run dev    # http://localhost:5173 (proxies API to :8000)
pnpm run build  # production bundle for FastAPI / Docker
```

## Demo scripts

- `./scripts/demo_hydra.sh` — external attack simulation (see `docs/hydra-demo.md`)
- `uv run python scripts/seed_db.py` — re-seed database
