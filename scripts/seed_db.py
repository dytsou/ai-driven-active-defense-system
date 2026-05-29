"""Database seed script for demo accounts and pre-seeded baseline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import BehavioralProfile, MfaMethod, User, UserRole
from app.db.session import SessionLocal, engine

DEMO1_BASELINE = {
    "dwell_mean": 95.0,
    "dwell_std": 12.0,
    "flight_mean": 110.0,
    "flight_std": 18.0,
    "hesitation_count": 0,
}


def seed_database(db: Session, cfg: Settings = settings) -> None:
    users = [
        {
            "username": "admin",
            "email": "admin@active-defense.local",
            "password": cfg.seed_admin_password,
            "role": UserRole.ADMIN.value,
        },
        {
            "username": "demo1",
            "email": "demo1@active-defense.local",
            "password": cfg.seed_demo1_password,
            "role": UserRole.USER.value,
        },
        {
            "username": "demo2",
            "email": "demo2@active-defense.local",
            "password": cfg.seed_demo2_password,
            "role": UserRole.USER.value,
        },
    ]

    for spec in users:
        existing = db.query(User).filter(User.username == spec["username"]).one_or_none()
        if existing:
            continue
        user = User(
            username=spec["username"],
            email=spec["email"],
            password_hash=hash_password(spec["password"]),
            role=spec["role"],
            mfa_method=MfaMethod.EMAIL.value,
        )
        db.add(user)
        db.flush()

        if spec["username"] == "demo1":
            db.add(
                BehavioralProfile(
                    user_id=user.id,
                    keystroke_baseline=DEMO1_BASELINE,
                    sample_count=1,
                )
            )

    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
        print("Seed complete: admin, demo1 (with baseline), demo2")
    finally:
        db.close()


if __name__ == "__main__":
    main()
