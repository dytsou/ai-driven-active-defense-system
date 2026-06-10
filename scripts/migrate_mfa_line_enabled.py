"""Add users.mfa_line_enabled (default true)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import engine

MIGRATION_STATEMENTS = [
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS mfa_line_enabled BOOLEAN NOT NULL DEFAULT TRUE
    """,
    """
    UPDATE users
    SET mfa_line_enabled = TRUE
    WHERE mfa_line_enabled IS NULL
    """,
]


def main() -> None:
    with engine.begin() as conn:
        for statement in MIGRATION_STATEMENTS:
            conn.execute(text(statement.strip()))
    print("MFA line preference migration complete.")


if __name__ == "__main__":
    main()
