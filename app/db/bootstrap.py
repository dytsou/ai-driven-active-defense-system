"""Idempotent database schema sync and demo account seeding for all environments."""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from scripts.seed_db import seed_database

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


def bootstrap_database() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for statement in MIGRATION_STATEMENTS:
            conn.execute(text(statement.strip()))
    with SessionLocal() as db:
        seed_database(db, settings)
