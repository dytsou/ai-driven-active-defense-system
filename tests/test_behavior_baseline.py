import pytest

from app.schemas.auth import KeystrokePayload, KeystrokeTiming
from app.services.behavior_service import BehaviorService


def _normal_keystroke() -> KeystrokePayload:
    return KeystrokePayload(
        present=True,
        timing=KeystrokeTiming(
            dwell_times=[95, 92, 98, 94],
            flight_times=[110, 108, 112, 109],
        ),
    )


def _anomalous_keystroke() -> KeystrokePayload:
    return KeystrokePayload(
        present=True,
        timing=KeystrokeTiming(
            dwell_times=[200, 210, 205, 215],
            flight_times=[250, 260, 255, 265],
        ),
    )


def test_compute_features_from_keystroke():
    service = BehaviorService()
    features = service.extract_features(_normal_keystroke())
    assert features["dwell_mean"] == pytest.approx(94.75, rel=0.01)
    assert features["flight_mean"] == pytest.approx(109.75, rel=0.01)


def test_deviation_zero_when_no_baseline():
    service = BehaviorService()
    deviation = service.compute_deviation(_normal_keystroke(), None)
    assert deviation == 0.0


def test_deviation_high_for_anomalous_timing():
    service = BehaviorService()
    baseline = {
        "dwell_mean": 95.0,
        "dwell_std": 12.0,
        "flight_mean": 110.0,
        "flight_std": 18.0,
    }
    deviation = service.compute_deviation(_anomalous_keystroke(), baseline)
    assert deviation >= 0.35


def test_create_baseline_on_first_success(seeded_db):
    from app.db.models import BehavioralProfile, User

    service = BehaviorService()
    demo2 = seeded_db.query(User).filter(User.username == "demo2").one()
    profile = seeded_db.query(BehavioralProfile).filter(BehavioralProfile.user_id == demo2.id).one_or_none()
    assert profile is None

    service.update_baseline(seeded_db, demo2, _normal_keystroke())
    profile = seeded_db.query(BehavioralProfile).filter(BehavioralProfile.user_id == demo2.id).one()
    assert profile.sample_count == 1
    assert profile.keystroke_baseline["dwell_mean"] > 0


def test_auth_uses_baseline_deviation_for_mfa(auth_client, seeded_db):
    from app.core.config import settings

    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo1",
            "password": settings.seed_demo1_password,
            "keystroke": _anomalous_keystroke().model_dump(),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "mfa_required"
