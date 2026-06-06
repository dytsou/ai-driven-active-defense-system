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

Login for 9-digit usernames verifies the **NYCU portal password** via server-side HTTP (not a separate local password). Incomplete registration returns `registration_required` (403).

Legacy OAuth login routes (`/api/v1/auth/oauth/nycu/start|callback`) redirect to `/register`.

## NYCU OAuth

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

When configured, submitting the login form with a registered NYCU account (any 9-digit username except seed demo accounts) uses **server-side HTTP** to verify the NYCU portal password, complete OAuth, and return `success` with a session cookie (or `mfa_required` when adaptive risk triggers).

Flow:

1. `POST /api/v1/auth/login` → server verifies NYCU portal credentials via httpx → session cookie or MFA challenge
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

Local Docker uses **Mailhog** (`SMTP_HOST=mailhog`, port `1025`) — view messages at http://localhost:8025.

For production, configure **Brevo SMTP** in `.env`:

1. Sign in at [Brevo](https://www.brevo.com/) → **SMTP & API** → create an **SMTP key**
2. Add and verify a **sender** (`SMTP_FROM` must match a verified sender)
3. Set:

| Variable        | Local (Mailhog) | Production (Brevo)               |
| --------------- | --------------- | -------------------------------- |
| `SMTP_HOST`     | `mailhog`       | `smtp-relay.brevo.com`           |
| `SMTP_PORT`     | `1025`          | `587` (or `465` with SSL)        |
| `SMTP_USE_TLS`  | `false`         | `true` (port 587)                |
| `SMTP_USE_SSL`  | `false`         | `true` (port 465, optional)      |
| `SMTP_USER`     | _(empty)_       | Your Brevo login email           |
| `SMTP_PASSWORD` | _(empty)_       | Brevo **SMTP key** (not web pwd) |
| `SMTP_FROM`     | any local addr  | Verified sender in Brevo         |

Example:

```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USER=you@example.com
SMTP_PASSWORD=xsmtpsib-...
SMTP_FROM=noreply@yourdomain.com
```

**Docker note:** `docker-compose.yml` sets `SMTP_HOST: mailhog` on the app service, which overrides `.env`. Remove or comment that line when testing Brevo inside Docker.

MFA send responses include a masked `delivery_target` (e.g. `111***073@nycu.edu.tw`) so the Portal can confirm where the code was sent without exposing the full address.

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
