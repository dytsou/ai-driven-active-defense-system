from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, LoginAttempt, RegistrationStatus, ThreatSignal, User


def bucket_minutes_for_window(hours: int) -> int:
    if hours <= 1:
        return 5
    if hours <= 24:
        return 60
    return 1440


def floor_to_bucket(ts: datetime, since: datetime, bucket_minutes: int) -> datetime:
    ts = ts.astimezone(timezone.utc)
    since = since.astimezone(timezone.utc)
    elapsed_minutes = int((ts - since).total_seconds() // 60)
    bucket_index = max(0, elapsed_minutes // bucket_minutes)
    return since + timedelta(minutes=bucket_index * bucket_minutes)


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def generate(self, *, hours: int | None = 24) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=hours) if hours and hours > 0 else None

        return {
            "generated_at": now.isoformat(),
            "window_hours": hours if hours and hours > 0 else None,
            "window_start": since.isoformat() if since else None,
            "users": self._user_summary(),
            "login_attempts": self._login_summary(since, hours if hours and hours > 0 else 24),
            "audit_events": self._audit_summary(since),
            "threat_signals": self._threat_summary(since),
        }

    def _user_summary(self) -> dict[str, Any]:
        total = self.db.query(func.count(User.id)).scalar() or 0
        registered = (
            self.db.query(func.count(User.id))
            .filter(User.registration_status == RegistrationStatus.COMPLETE.value)
            .scalar()
            or 0
        )
        line_bound = (
            self.db.query(func.count(User.id)).filter(User.line_user_id.isnot(None)).scalar() or 0
        )
        line_mfa_on = (
            self.db.query(func.count(User.id))
            .filter(User.line_user_id.isnot(None), User.mfa_line_enabled.is_(True))
            .scalar()
            or 0
        )
        nycu_bound = (
            self.db.query(func.count(User.id))
            .filter(User.nycu_oauth_subject.isnot(None))
            .scalar()
            or 0
        )
        return {
            "total": total,
            "registration_complete": registered,
            "nycu_bound": nycu_bound,
            "line_bound": line_bound,
            "line_mfa_enabled": line_mfa_on,
        }

    def _login_query(self, since: datetime | None):
        query = self.db.query(LoginAttempt)
        if since is not None:
            query = query.filter(LoginAttempt.created_at >= since)
        return query

    def _login_summary(self, since: datetime | None, window_hours: int) -> dict[str, Any]:
        base = self._login_query(since)
        total = base.count()
        successes = base.filter(LoginAttempt.success.is_(True)).count()

        by_action = (
            self._login_query(since)
            .with_entities(LoginAttempt.action_taken, func.count(LoginAttempt.id))
            .group_by(LoginAttempt.action_taken)
            .all()
        )
        by_risk_level = (
            self._login_query(since)
            .filter(LoginAttempt.risk_level.isnot(None))
            .with_entities(LoginAttempt.risk_level, func.count(LoginAttempt.id))
            .group_by(LoginAttempt.risk_level)
            .all()
        )
        top_usernames = (
            self._login_query(since)
            .with_entities(LoginAttempt.username, func.count(LoginAttempt.id))
            .group_by(LoginAttempt.username)
            .order_by(func.count(LoginAttempt.id).desc())
            .limit(10)
            .all()
        )
        top_ips = (
            self._login_query(since)
            .with_entities(LoginAttempt.ip_address, func.count(LoginAttempt.id))
            .group_by(LoginAttempt.ip_address)
            .order_by(func.count(LoginAttempt.id).desc())
            .limit(10)
            .all()
        )
        avg_risk = (
            self._login_query(since)
            .filter(LoginAttempt.risk_score.isnot(None))
            .with_entities(func.avg(LoginAttempt.risk_score))
            .scalar()
        )

        return {
            "total": total,
            "successes": successes,
            "success_rate": round(successes / total, 4) if total else 0.0,
            "avg_risk_score": round(float(avg_risk), 4) if avg_risk is not None else None,
            "by_action": {action or "unknown": count for action, count in by_action},
            "by_risk_level": {level: count for level, count in by_risk_level},
            "top_usernames": [{"username": u, "count": c} for u, c in top_usernames],
            "top_ips": [{"ip_address": ip, "count": c} for ip, c in top_ips],
            "timeline": self._login_timeline(since, window_hours),
        }

    def _login_timeline(self, since: datetime | None, window_hours: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if since is None:
            since = now - timedelta(hours=window_hours)

        bucket_minutes = bucket_minutes_for_window(window_hours)
        bucket_delta = timedelta(minutes=bucket_minutes)
        num_buckets = max(1, math.ceil((now - since).total_seconds() / bucket_delta.total_seconds()))

        buckets: dict[datetime, dict[str, Any]] = {}
        for index in range(num_buckets):
            bucket_start = since + timedelta(minutes=index * bucket_minutes)
            buckets[bucket_start] = {
                "bucket_start": bucket_start.isoformat(),
                "total": 0,
                "successes": 0,
            }

        rows = (
            self._login_query(since)
            .with_entities(LoginAttempt.created_at, LoginAttempt.success)
            .all()
        )
        for created_at, success in rows:
            if created_at is None:
                continue
            bucket_start = floor_to_bucket(created_at, since, bucket_minutes)
            if bucket_start not in buckets:
                continue
            buckets[bucket_start]["total"] += 1
            if success:
                buckets[bucket_start]["successes"] += 1

        return [buckets[since + timedelta(minutes=index * bucket_minutes)] for index in range(num_buckets)]

    def _audit_query(self, since: datetime | None):
        query = self.db.query(AuditEvent)
        if since is not None:
            query = query.filter(AuditEvent.created_at >= since)
        return query

    def _audit_summary(self, since: datetime | None) -> dict[str, Any]:
        total = self._audit_query(since).count()
        by_type = (
            self._audit_query(since)
            .with_entities(AuditEvent.event_type, func.count(AuditEvent.id))
            .group_by(AuditEvent.event_type)
            .order_by(func.count(AuditEvent.id).desc())
            .all()
        )
        return {
            "total": total,
            "by_type": {event_type: count for event_type, count in by_type},
        }

    def _threat_query(self, since: datetime | None):
        query = self.db.query(ThreatSignal)
        if since is not None:
            query = query.filter(ThreatSignal.created_at >= since)
        return query

    def _threat_summary(self, since: datetime | None) -> dict[str, Any]:
        total = self._threat_query(since).count()
        by_severity = (
            self._threat_query(since)
            .with_entities(ThreatSignal.severity, func.count(ThreatSignal.id))
            .group_by(ThreatSignal.severity)
            .all()
        )
        by_signal = (
            self._threat_query(since)
            .with_entities(ThreatSignal.signal_type, func.count(ThreatSignal.id))
            .group_by(ThreatSignal.signal_type)
            .order_by(func.count(ThreatSignal.id).desc())
            .limit(10)
            .all()
        )
        top_ips = (
            self._threat_query(since)
            .with_entities(ThreatSignal.source_ip, func.count(ThreatSignal.id))
            .group_by(ThreatSignal.source_ip)
            .order_by(func.count(ThreatSignal.id).desc())
            .limit(10)
            .all()
        )
        return {
            "total": total,
            "by_severity": {severity: count for severity, count in by_severity},
            "by_signal_type": {signal: count for signal, count in by_signal},
            "top_ips": [{"ip_address": ip, "count": c} for ip, c in top_ips],
        }
