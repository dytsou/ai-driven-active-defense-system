from app.services.report_service import ReportService
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
