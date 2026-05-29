from fastapi.testclient import TestClient

from app.core.config import settings


def test_api_login_with_fake_keystroke_flag_still_requires_mfa(auth_client: TestClient, seeded_db):
    """Single dwell sample is normalized server-side; cannot satisfy present=true alone."""
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo1",
            "password": settings.seed_demo1_password,
            "keystroke": {"present": True, "timing": {"dwell_times": [95], "flight_times": [110]}},
        },
    )
    assert response.json()["status"] == "mfa_required"
