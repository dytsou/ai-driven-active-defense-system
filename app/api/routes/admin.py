import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.models import User, UserRole
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.api.routes.auth import get_auth_service

router = APIRouter(prefix="/admin/api", tags=["admin"])


def _require_admin(request: Request, auth: AuthService) -> User:
    session_id = request.cookies.get("session_id")
    user = auth.get_current_user(session_id)
    if not user:
        raise PermissionError("unauthenticated")
    if user.role != UserRole.ADMIN.value:
        raise PermissionError("forbidden")
    return user


@router.get("/events")
def list_events(
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthService = Depends(get_auth_service),
):
    try:
        _require_admin(request, auth)
    except PermissionError as exc:
        if str(exc) == "unauthenticated":
            return Response(status_code=401)
        return Response(status_code=403)

    events = EventService(db).list_events()
    return {
        "events": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "actor_username": event.actor_username,
                "ip_address": event.ip_address,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
    }
