from datetime import datetime, timedelta, timezone

from app.services.report_service import ReportService, bucket_minutes_for_window, floor_to_bucket
from app.db.models import AuditEvent, LoginAttempt, User, UserRole


def test_report_aggregates_login_and_audit(seeded_db):
    seeded_db.add(
        LoginAttempt(
            username="demo1",
            ip_address="203.0.113.99",
            success=False,
            action_taken="step_up_mfa",
            risk_score=0.85,
            risk_level="high",
            ml_source="ml_aggregate",
        )
    )
    seeded_db.add(
        AuditEvent(
            event_type="mfa_required",
            actor_username="demo1",
            ip_address="203.0.113.99",
            payload={"risk_score": 0.85},
        )
    )
    seeded_db.commit()

    report = ReportService(seeded_db).generate(hours=0)

    assert report["users"]["total"] >= 3
    assert report["login_attempts"]["total"] >= 1
    assert report["login_attempts"]["by_action"].get("step_up_mfa", 0) >= 1
    assert report["audit_events"]["by_type"].get("mfa_required", 0) >= 1


def test_report_includes_login_timeline(seeded_db):
    now = datetime.now(timezone.utc)
    seeded_db.add(
        LoginAttempt(
            username="timeline-user",
            ip_address="203.0.113.50",
            success=True,
            created_at=now - timedelta(minutes=10),
        )
    )
    seeded_db.add(
        LoginAttempt(
            username="timeline-user",
            ip_address="203.0.113.50",
            success=False,
            risk_level="high",
            created_at=now - timedelta(minutes=20),
        )
    )
    seeded_db.commit()

    report = ReportService(seeded_db).generate(hours=1)
    timeline = report["login_attempts"]["timeline"]

    assert isinstance(timeline, list)
    assert len(timeline) >= 1
    assert sum(point["total"] for point in timeline) >= 2
    assert report["login_attempts"]["by_risk_level"].get("high", 0) >= 1


def test_timeline_includes_attempts_at_window_end(seeded_db):
    now = datetime.now(timezone.utc)
    seeded_db.add(
        LoginAttempt(
            username="edge-user",
            ip_address="203.0.113.88",
            success=True,
            created_at=now,
        )
    )
    seeded_db.commit()

    report = ReportService(seeded_db).generate(hours=1)
    timeline = report["login_attempts"]["timeline"]

    assert timeline
    assert sum(point["total"] for point in timeline) >= 1


def test_all_time_report_has_empty_timeline(seeded_db):
    report = ReportService(seeded_db).generate(hours=0)
    assert report["login_attempts"]["timeline"] == []


def test_bucket_helpers():
    assert bucket_minutes_for_window(1) == 5
    assert bucket_minutes_for_window(24) == 60
    assert bucket_minutes_for_window(168) == 1440

    since = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    ts = since + timedelta(minutes=17)
    assert floor_to_bucket(ts, since, 5) == since + timedelta(minutes=15)
