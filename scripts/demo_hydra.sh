#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-http://localhost:8000}"
USER_LIST="${USER_LIST:-demo1,demo2}"
PASSWORDS="${PASSWORDS:-Demo123!,wrong1,wrong2,wrong3}"

echo "Active Defense Hydra-style login flood against ${TARGET}"
echo "Press Ctrl+C to stop."

while true; do
  for user in ${USER_LIST//,/ }; do
    for pass in ${PASSWORDS//,/ }; do
      curl -s -o /dev/null -w "%{http_code}\n" \
        -X POST "${TARGET}/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -H "X-Forwarded-For: 203.0.113.99" \
        -d "{\"username\":\"${user}\",\"password\":\"${pass}\"}" || true
    done
  done
  sleep 0.2
done
