from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import BehavioralProfile, User
from scripts.seed_db import seed_database


def test_health_returns_200(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seed_creates_three_users(seeded_db):
    users = seeded_db.query(User).order_by(User.username).all()
    usernames = {user.username for user in users}
    assert usernames == {"admin", "demo1", "demo2"}


def test_seed_assigns_admin_role(seeded_db):
    admin = seeded_db.query(User).filter(User.username == "admin").one()
    assert admin.role == "admin"


def test_demo1_has_preseeded_baseline(seeded_db):
    demo1 = seeded_db.query(User).filter(User.username == "demo1").one()
    profile = seeded_db.query(BehavioralProfile).filter(BehavioralProfile.user_id == demo1.id).one()
    assert profile.sample_count >= 1
    assert profile.keystroke_baseline is not None
    assert "dwell_mean" in profile.keystroke_baseline
    assert "flight_mean" in profile.keystroke_baseline


def test_demo2_has_no_baseline(seeded_db):
    demo2 = seeded_db.query(User).filter(User.username == "demo2").one()
    profile = (
        seeded_db.query(BehavioralProfile).filter(BehavioralProfile.user_id == demo2.id).one_or_none()
    )
    assert profile is None


def test_seed_is_idempotent(seeded_db):
    seed_database(seeded_db, settings)
    assert seeded_db.query(User).count() == 3
