#!/usr/bin/env bash
# Sync .env with GitHub Actions secrets (one secret per variable).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
TEMPLATE="${ROOT}/.env.example"
CI_FILE="${ROOT}/.github/workflows/ci.yml"
CI_START='      # sync-env-secrets:start'
CI_END='      # sync-env-secrets:end'

usage() {
  cat <<'EOF'
Usage:
  sync_env_github.sh push [--env-file PATH] [--repo owner/repo] [--include-empty]
  sync_env_github.sh restore [--template PATH] [--output PATH]
  sync_env_github.sh print-ci-env [--template PATH]
  sync_env_github.sh patch-ci [--template PATH]
EOF
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_quotes() {
  local value="$1"
  if ((${#value} >= 2)); then
    local first="${value:0:1}"
    local last="${value: -1}"
    if [[ "$first" == "$last" && ( "$first" == '"' || "$first" == "'" ) ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi
  printf '%s' "$value"
}

parse_env_entries() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "missing file: $file" >&2
    return 1
  fi

  while IFS= read -r raw || [[ -n "$raw" ]]; do
    local line
    line="$(trim "$raw")"
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ "$line" == export* ]]; then
      line="$(trim "${line#export}")"
    fi
    [[ "$line" != *"="* ]] && continue

    local key value
    key="$(trim "${line%%=*}")"
    value="$(strip_quotes "$(trim "${line#*=}")")"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    printf '%s\037%s\n' "$key" "$value"
  done <"$file"
}

list_template_keys() {
  parse_env_entries "$1" | while IFS=$'\037' read -r key _; do
    printf '%s\n' "$key"
  done
}

cmd_push() {
  local file="$ENV_FILE"
  local repo=""
  local include_empty=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --env-file)
        file="$2"
        shift 2
        ;;
      --repo)
        repo="$2"
        shift 2
        ;;
      --include-empty)
        include_empty=true
        shift
        ;;
      *)
        echo "unknown push arg: $1" >&2
        return 1
        ;;
    esac
  done

  local pushed=0 skipped=0
  local entries
  entries="$(parse_env_entries "$file")" || return 1
  if [[ -z "$entries" ]]; then
    echo "No variables found in $file" >&2
    return 1
  fi

  while IFS=$'\037' read -r key value; do
    if [[ -z "$value" && "$include_empty" != true ]]; then
      skipped=$((skipped + 1))
      continue
    fi
    if [[ -n "$repo" ]]; then
      printf '%s' "$value" | gh secret set "$key" --repo "$repo"
    else
      printf '%s' "$value" | gh secret set "$key"
    fi
    echo "set $key"
    pushed=$((pushed + 1))
  done <<<"$entries"

  echo "Done: ${pushed} secrets set, ${skipped} empty skipped"
}

cmd_restore() {
  local template="$TEMPLATE"
  local output="$ENV_FILE"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --template)
        template="$2"
        shift 2
        ;;
      --output)
        output="$2"
        shift 2
        ;;
      *)
        echo "unknown restore arg: $1" >&2
        return 1
        ;;
    esac
  done

  declare -A defaults=()
  while IFS=$'\037' read -r key value; do
    defaults["$key"]="$value"
  done < <(parse_env_entries "$template")

  local secret_count=0
  : >"$output"
  while IFS= read -r key || [[ -n "$key" ]]; do
    [[ -z "$key" ]] && continue
    local val="${defaults[$key]:-}"
    if [[ -n "${!key-}" ]]; then
      val="${!key}"
      secret_count=$((secret_count + 1))
    fi
    printf '%s=%s\n' "$key" "$val" >>"$output"
  done < <(list_template_keys "$template")

  echo "Wrote ${output} (${secret_count}/$(wc -l < <(list_template_keys "$template") | tr -d ' ') values from environment)"
}

build_ci_env_block() {
  local template="$1"
  local key
  printf '%s\n' "$CI_START"
  while IFS= read -r key || [[ -n "$key" ]]; do
    [[ -z "$key" ]] && continue
    printf '          %s: ${{' 'secrets.%s }}' '\n' "$key" "$key"
  done < <(list_template_keys "$template")
  printf '%s\n' "$CI_END"
}

cmd_print_ci_env() {
  local template="$TEMPLATE"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --template)
        template="$2"
        shift 2
        ;;
      *)
        echo "unknown print-ci-env arg: $1" >&2
        return 1
        ;;
    esac
  done
  build_ci_env_block "$template"
}

cmd_patch_ci() {
  local template="$TEMPLATE"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --template)
        template="$2"
        shift 2
        ;;
      *)
        echo "unknown patch-ci arg: $1" >&2
        return 1
        ;;
    esac
  done

  if [[ ! -f "$CI_FILE" ]]; then
    echo "missing file: $CI_FILE" >&2
    return 1
  fi
  if ! grep -qF "$CI_START" "$CI_FILE" || ! grep -qF "$CI_END" "$CI_FILE"; then
    echo "Markers not found in $CI_FILE; add Restore .env step with markers" >&2
    return 1
  fi

  local block_file patched_file key_count
  block_file="$(mktemp)"
  patched_file="$(mktemp)"
  build_ci_env_block "$template" >"$block_file"
  key_count="$(list_template_keys "$template" | wc -l | tr -d ' ')"

  awk -v start="$CI_START" -v end="$CI_END" -v blockfile="$block_file" '
    $0 == start {
      while ((getline line < blockfile) > 0) print line
      close(blockfile)
      skip = 1
      next
    }
    $0 == end {
      skip = 0
      next
    }
    !skip { print }
  ' "$CI_FILE" >"$patched_file"

  mv "$patched_file" "$CI_FILE"
  rm -f "$block_file"
  echo "Patched ${CI_FILE} with ${key_count} secret mappings"
}

main() {
  local command="${1:-}"
  shift || true

  case "$command" in
    push) cmd_push "$@" ;;
    restore) cmd_restore "$@" ;;
    print-ci-env) cmd_print_ci_env "$@" ;;
    patch-ci) cmd_patch_ci "$@" ;;
    -h | --help | help | "") usage ;;
    *)
      echo "unknown command: $command" >&2
      usage >&2
      return 1
      ;;
  esac
}

main "$@"
