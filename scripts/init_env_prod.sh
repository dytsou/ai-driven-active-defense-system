#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="${ROOT}/.env.example"
TARGET="${ROOT}/.env.prod"

if [[ -f "$TARGET" ]]; then
  echo ".env.prod already exists — not overwriting"
  exit 0
fi

cp "$EXAMPLE" "$TARGET"
echo "Created ${TARGET} from .env.example"
echo "Edit production values (Brevo SMTP, APP_DEBUG=false, OAuth, …), then:"
echo "  bash scripts/sync_env_github.sh push-prod"
