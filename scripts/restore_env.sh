#!/usr/bin/env bash
set -euo pipefail

# CI/tests: use safe defaults from .env.example (not production secrets).
cp .env.example .env
echo "Using .env.example for CI/tests"
