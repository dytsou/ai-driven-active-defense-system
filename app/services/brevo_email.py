import logging
import time

import httpx

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (0.5, 1.0)
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _sanitize_api_error(status_code: int, body: str) -> str:
    snippet = (body or "").strip().replace("\n", " ")
    if len(snippet) > 120:
        snippet = f"{snippet[:117]}..."
    return f"status={status_code} detail={snippet or 'no-body'}"


def send_transactional_email(
    *,
    api_key: str,
    sender: str,
    recipient: str,
    subject: str,
    text_content: str,
    timeout: float = 10.0,
) -> tuple[bool, str | None]:
    payload = {
        "sender": {"email": sender},
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": text_content,
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    last_error: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(BREVO_SEND_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            last_error = "api_transport_error"
            logger.warning(
                "Brevo API transport error attempt=%s/%s error=%s",
                attempt,
                MAX_ATTEMPTS,
                exc.__class__.__name__,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
            continue

        if response.status_code in (200, 201, 202):
            return True, None

        last_error = "api_error"
        logger.error(
            "Brevo API refused delivery attempt=%s/%s %s",
            attempt,
            MAX_ATTEMPTS,
            _sanitize_api_error(response.status_code, response.text),
        )
        if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
            continue
        return False, last_error

    return False, last_error or "api_transport_error"
