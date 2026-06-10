#!/usr/bin/env python3
"""Apply schema migrations and seed admin/demo accounts (idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.bootstrap import bootstrap_database


def main() -> None:
    bootstrap_database()
    print("Database bootstrap complete: schema synced, admin/demo1/demo2 seeded.")


if __name__ == "__main__":
    main()
