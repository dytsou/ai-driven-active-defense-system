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

Any 9-digit username can be auto-provisioned on first password login (email `{username}@nycu.edu.tw`).

## NYCU OAuth (optional)

Reference: [NYCU-SDC/clustron-backend](https://github.com/NYCU-SDC/clustron-backend) (`internal/auth/oauthprovider/nycu.go`).

Register a redirect URL with NYCU ID:

`{BASE_URL}/api/v1/auth/oauth/nycu/callback`

Set in `.env` (copy from `.env.example`; do not commit real secrets):

| Variable                   | Example                 | Purpose                                  |
| -------------------------- | ----------------------- | ---------------------------------------- |
| `BASE_URL`                 | `http://localhost:8000` | Public app URL (used for OAuth redirect) |
| `NYCU_OAUTH_CLIENT_ID`     | _(from NYCU)_           | OAuth client ID                          |
| `NYCU_OAUTH_CLIENT_SECRET` | _(from NYCU)_           | OAuth client secret                      |

Local redirect URI (must match NYCU application whitelist exactly):

`http://localhost:8000/api/v1/auth/oauth/nycu/callback`

Manual token exchange for debugging (replace `YOUR_AUTHORIZATION_CODE` with the `code` query param from the callback):

```bash
curl -X POST https://id.nycu.edu.tw/o/token/ \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost:8000/api/v1/auth/oauth/nycu/callback" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

When configured, submitting the login form with a NYCU account (any username except seed demo accounts) uses **server-side HTTP** to sign in at NYCU (`/accounts/login/`), complete OAuth, and return `success` with a session cookie. The browser stays on the Portal and navigates directly to `/me`.

Flow:

1. `POST /api/v1/auth/login` → server completes NYCU login + OAuth via httpx → session cookie → frontend navigates to `/me`
2. `GET /api/v1/auth/oauth/nycu/callback` → used by manual OAuth start (`/api/v1/auth/oauth/nycu/start`) or the HTTP login redirect chain

Optional env:

| Variable                         | Default | Purpose                          |
| -------------------------------- | ------- | -------------------------------- |
| `NYCU_OAUTH_HTTP_TIMEOUT_SECONDS` | `60`    | NYCU login/OAuth HTTP timeout    |

If NYCU login fails, the Portal shows an error message on the login page.

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
