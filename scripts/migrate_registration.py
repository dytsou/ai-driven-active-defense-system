"""Add registration columns and partial unique indexes for identity binding."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import engine

MIGRATION_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_status VARCHAR(16) NOT NULL DEFAULT 'complete'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS nycu_oauth_subject VARCHAR(64)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_users_line_user_id
    ON users (line_user_id)
    WHERE line_user_id IS NOT NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_users_nycu_oauth_subject
    ON users (nycu_oauth_subject)
    WHERE nycu_oauth_subject IS NOT NULL
    """,
    """
    UPDATE users
    SET registration_status = 'complete'
    WHERE username IN ('admin', 'demo1', 'demo2')
    """,
    """
    UPDATE users
    SET registration_status = 'complete'
    WHERE username ~ '^[0-9]{9}$'
      AND (nycu_oauth_subject IS NOT NULL OR line_user_id IS NOT NULL)
    """,
]


def main() -> None:
    with engine.begin() as conn:
        for statement in MIGRATION_STATEMENTS:
            conn.execute(text(statement.strip()))
    print("Registration migration complete.")


if __name__ == "__main__":
    main()
