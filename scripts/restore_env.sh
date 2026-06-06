#!/usr/bin/env bash
set -euo pipefail

# Build .env from GitHub Actions secrets (injected as env vars) with .env.example defaults.
bash scripts/sync_env_github.sh restore
