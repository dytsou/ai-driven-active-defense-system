#!/usr/bin/env bash
set -euo pipefail

# Build .env from GitHub Actions secrets (injected as env vars) with .env.example defaults.
python3 scripts/sync_env_github.py restore
