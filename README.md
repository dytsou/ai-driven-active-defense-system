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

`make up` loads variables from `.env` via `docker compose --env-file .env`.

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

NYCU students and staff must **register once** (NYCU OAuth + LINE) before logging in. Seed accounts (`admin`, `demo1`, `demo2`) use local passwords and email-only MFA.

### Registration migration

After pulling registration changes, run:

```bash
uv run python scripts/migrate_registration.py
uv run python scripts/seed_db.py
```

Existing 9-digit users are grandfathered to `registration_status=complete` without retroactive LINE binding.

## Registration (NYCU + LINE)

First-time users bind NYCU OAuth and LINE at `/register`:

1. `POST /api/v1/auth/register/start` → NYCU authorization URL
2. NYCU callback → user row with `registration_status=pending_line`
3. LINE Login → bind `line_user_id`
4. User confirms LINE friend → `POST /api/v1/auth/register/complete`

Login for registered users skips the portal password check and runs keystroke + adaptive risk (MFA when risk is elevated). Incomplete registration returns `registration_required` (403).

Legacy OAuth login routes (`/api/v1/auth/oauth/nycu/start|callback`) redirect to `/register`.

## NYCU OAuth

Register these redirect URLs with NYCU ID (must match whitelist exactly):

- Registration: `{BASE_URL}/api/v1/auth/register/nycu/callback`
- Legacy: `{BASE_URL}/api/v1/auth/oauth/nycu/callback`

Set in `.env` or `.env.prod` (copy from `.env.example`; do not commit secrets):

| Variable                   | Example                 | Purpose                                  |
| -------------------------- | ----------------------- | ---------------------------------------- |
| `BASE_URL`                 | `http://localhost:8000` | Public app URL (used for OAuth redirect) |
| `NYCU_OAUTH_CLIENT_ID`     | _(from NYCU)_           | OAuth client ID                          |
| `NYCU_OAUTH_CLIENT_SECRET` | _(from NYCU)_           | OAuth client secret                      |

Local redirect URIs:

```
http://localhost:8000/api/v1/auth/register/nycu/callback
http://localhost:8000/api/v1/auth/oauth/nycu/callback
```

Manual token exchange for debugging (replace placeholders):

```bash
curl -X POST https://id.nycu.edu.tw/o/token/ \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost:8000/api/v1/auth/oauth/nycu/callback" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

When configured, registered NYCU accounts (9-digit usernames) log in through the unified risk path: keystroke analysis → allow, MFA, or block.

Flow:

1. `POST /api/v1/auth/login` → session cookie, `mfa_required`, or block
2. `GET /api/v1/auth/oauth/nycu/callback` → legacy route; redirects to `/register`

Optional env:

| Variable                          | Default | Purpose                       |
| --------------------------------- | ------- | ----------------------------- |
| `NYCU_OAUTH_HTTP_TIMEOUT_SECONDS` | `60`    | NYCU login/OAuth HTTP timeout |

### LINE Login (registration)

| Variable                           | Example                                                    | Purpose                         |
| ---------------------------------- | ---------------------------------------------------------- | ------------------------------- |
| `LINE_LOGIN_CHANNEL_ID`            | _(from LINE Developers)_                                   | LINE Login channel ID           |
| `LINE_LOGIN_CHANNEL_SECRET`        | _(from LINE Developers)_                                   | LINE Login channel secret       |
| `LINE_LOGIN_CALLBACK_URL`          | `http://localhost:8000/api/v1/auth/register/line/callback` | OAuth redirect URI              |
| `LINE_OFFICIAL_ACCOUNT_URL`        | `https://line.me/R/ti/p/@...`                              | Friend-add link shown in wizard |
| `FRONTEND_BASE_URL`                | `http://localhost:8000`                                    | Registration redirect base      |
| `REGISTRATION_SESSION_TTL_SECONDS` | `900`                                                      | Redis registration state TTL    |
| `RATE_LIMIT_REGISTER_PER_MIN`      | `20`                                                       | Per-IP registration rate limit  |

If NYCU login fails, the Portal shows an error message on the login page.

NYCU OAuth syncs the user's profile email into `users.email`. When adaptive MFA triggers on a later login, the OTP is sent to that address.

## MFA email (Brevo)

### Local (Mailhog)

With `APP_DEBUG=true` (default in `.env.example`), SMTP is routed to **Mailhog** regardless of `SMTP_*` — view messages at http://localhost:8025.

### Production (Brevo)

Set `APP_DEBUG=false` in `.env.prod` and configure Brevo:

1. Sign in at [Brevo](https://www.brevo.com/) → **SMTP & API** → **SMTP** tab → create an **SMTP key** (`xsmtpsib-...`)
2. Add and verify a **sender** (`SMTP_FROM` must match)
3. Under **Settings → Security → Authorized IPs**, allow your server IP or deactivate blocking for testing
4. Set:

| Variable        | Production (Brevo)                                |
| --------------- | ------------------------------------------------- |
| `SMTP_HOST`     | `smtp-relay.brevo.com`                            |
| `SMTP_PORT`     | `587` (TLS) or `465` (SSL)                        |
| `SMTP_USE_TLS`  | `true` (port 587)                                 |
| `SMTP_USE_SSL`  | `false` (or `true` with port 465)                 |
| `SMTP_USER`     | SMTP login from Brevo (e.g. `xxx@smtp-brevo.com`) |
| `SMTP_PASSWORD` | Brevo **SMTP key** (not API key `xkeysib-`)       |
| `SMTP_FROM`     | Verified sender in Brevo                          |

Example:

```env
APP_DEBUG=false
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USER=7xxxxx@smtp-brevo.com
SMTP_PASSWORD=xsmtpsib-...
SMTP_FROM=noreply@yourdomain.com
```

Docker loads env at runtime: `docker compose --env-file .env.prod up -d`.

MFA send responses include a masked `delivery_target` (e.g. `111***073@nycu.edu.tw`). With `APP_DEBUG=true`, the API may also return `debug_otp` for local testing.

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
- `bash scripts/init_env_prod.sh` — create `.env.prod` from `.env` or `.env.example`
- `bash scripts/sync_env_github.sh push-prod` — upload `.env.prod` to GitHub secrets
- `bash scripts/restore_env.sh` — CI helper: `cp .env.example .env`
