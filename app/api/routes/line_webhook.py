import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.services.line_messaging import LineMessagingService
from app.services.line_webhook_handler import LineWebhookHandler
from app.services.redis_client import get_redis_from_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/line", tags=["line"])


@router.post("/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    messaging = LineMessagingService()

    if not messaging.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid LINE webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    handler = LineWebhookHandler(get_redis_from_request(request), messaging=messaging)
    try:
        handler.handle_payload(payload)
    except Exception:
        logger.exception("LINE webhook handler failed")
        raise HTTPException(status_code=500, detail="Webhook handler error") from None

    return {"status": "ok"}
