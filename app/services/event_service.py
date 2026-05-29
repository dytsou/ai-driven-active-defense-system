from sqlalchemy.orm import Session

from app.db.models import AuditEvent


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        event_type: str,
        actor_username: str | None,
        ip_address: str | None,
        payload: dict,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            actor_username=actor_username,
            ip_address=ip_address,
            payload=payload,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(self, limit: int = 100) -> list[AuditEvent]:
        return (
            self.db.query(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )
