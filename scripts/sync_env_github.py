#!/usr/bin/env python3
"""Sync .env with GitHub Actions secrets (one secret per variable)."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"
DEFAULT_TEMPLATE = ROOT / ".env.example"
CI_FILE = ROOT / ".github" / "workflows" / "ci.yml"
CI_START = "      # sync-env-secrets:start"
CI_END = "      # sync-env-secrets:end"


def parse_dotenv(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    entries: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        entries.append((key, value))
    return entries


def template_keys(template: Path) -> list[str]:
    return [key for key, _ in parse_dotenv(template)]


def cmd_push(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file)
    entries = parse_dotenv(env_path)
    if not entries:
        print(f"No variables found in {env_path}", file=sys.stderr)
        return 1

    repo_args = ["--repo", args.repo] if args.repo else []
    pushed = skipped = 0

    for key, value in entries:
        if not value and not args.include_empty:
            skipped += 1
            continue
        cmd = ["gh", "secret", "set", key, *repo_args]
        subprocess.run(cmd, input=value, text=True, check=True)
        pushed += 1
        print(f"set {key}")

    print(f"Done: {pushed} secrets set, {skipped} empty skipped")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    template = Path(args.template)
    out = Path(args.output)
    keys = template_keys(template)
    template_map = dict(parse_dotenv(template))

    lines: list[str] = []
    for key in keys:
        if key in os.environ and os.environ[key] != "":
            value = os.environ[key]
        else:
            value = template_map.get(key, "")
        lines.append(f"{key}={value}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    secret_count = sum(1 for key in keys if key in os.environ and os.environ[key] != "")
    print(f"Wrote {out} ({secret_count}/{len(keys)} values from environment)")
    return 0


def ci_env_block(keys: list[str]) -> str:
    lines = [CI_START]
    for key in keys:
        lines.append(f"          {key}: ${{{{ secrets.{key} }}}}")
    lines.append(CI_END)
    return "\n".join(lines)


def cmd_print_ci_env(args: argparse.Namespace) -> int:
    keys = template_keys(Path(args.template))
    sys.stdout.write(ci_env_block(keys) + "\n")
    return 0


def cmd_patch_ci(args: argparse.Namespace) -> int:
    template = Path(args.template)
    keys = template_keys(template)
    block = ci_env_block(keys)

    text = CI_FILE.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(CI_START)}.*?{re.escape(CI_END)}",
        re.DOTALL,
    )
    if not pattern.search(text):
        print(f"Markers not found in {CI_FILE}; add Restore .env step with markers", file=sys.stderr)
        return 1

    updated = pattern.sub(block, text)
    CI_FILE.write_text(updated, encoding="utf-8")
    print(f"Patched {CI_FILE} with {len(keys)} secret mappings")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    push = sub.add_parser("push", help="Upload .env variables to GitHub secrets")
    push.add_argument("--env-file", default=str(DEFAULT_ENV))
    push.add_argument("--repo", default="", help="owner/repo (default: current gh repo)")
    push.add_argument(
        "--include-empty",
        action="store_true",
        help="Also create secrets for empty values",
    )
    push.set_defaults(func=cmd_push)

    restore = sub.add_parser("restore", help="Write .env from environment + .env.example defaults")
    restore.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    restore.add_argument("--output", default=str(DEFAULT_ENV))
    restore.set_defaults(func=cmd_restore)

    print_ci = sub.add_parser("print-ci-env", help="Print ci.yml env block for secrets")
    print_ci.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    print_ci.set_defaults(func=cmd_print_ci_env)

    patch_ci = sub.add_parser("patch-ci", help="Update ci.yml secret env block from .env.example")
    patch_ci.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    patch_ci.set_defaults(func=cmd_patch_ci)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
