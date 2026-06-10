#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/.env.prod"
SOURCE="${ROOT}/.env"

if [[ -f "$TARGET" ]]; then
  echo ".env.prod already exists — not overwriting"
  echo "Delete it first or edit in place, then: bash scripts/sync_env_github.sh push-prod"
  exit 0
fi

if [[ -f "$SOURCE" ]]; then
  cp "$SOURCE" "$TARGET"
  echo "Created ${TARGET} from .env"
else
  cp "${ROOT}/.env.example" "$TARGET"
  echo "Created ${TARGET} from .env.example"
fi

echo "Set production values (APP_DEBUG=false, BREVO_API_KEY, OAuth, …), then:"
echo "  bash scripts/sync_env_github.sh push-prod"
