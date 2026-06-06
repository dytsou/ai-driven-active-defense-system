#!/usr/bin/env bash
set -euo pipefail

# Build .env from GitHub Actions secrets (injected as env vars) with .env.example defaults.
uv run python scripts/sync_env_github.py restore
