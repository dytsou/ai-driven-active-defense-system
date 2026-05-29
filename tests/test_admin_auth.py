import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def test_admin_events_requires_auth(client: TestClient, seeded_db):
    response = client.get("/admin/api/events")
    assert response.status_code == 401


def test_admin_events_forbidden_for_demo_user(auth_client: TestClient, seeded_db):
    login = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "demo1",
            "password": settings.seed_demo1_password,
            "keystroke": {
                "present": True,
                "timing": {"dwell_times": [95, 92, 98], "flight_times": [110, 108, 112]},
            },
        },
    )
    session_id = login.cookies.get("session_id")
    response = auth_client.get("/admin/api/events", cookies={"session_id": session_id})
    assert response.status_code == 403


def test_admin_events_accessible_for_admin(auth_client: TestClient, seeded_db):
    login = auth_client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": settings.seed_admin_password,
            "keystroke": {
                "present": True,
                "timing": {"dwell_times": [95, 92, 98], "flight_times": [110, 108, 112]},
            },
        },
    )
    assert login.json()["status"] == "success"
    session_id = login.cookies.get("session_id")
    response = auth_client.get("/admin/api/events", cookies={"session_id": session_id})
    assert response.status_code == 200
    assert "events" in response.json()
