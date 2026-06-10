from unittest.mock import MagicMock, patch

import httpx

from app.services.brevo_email import send_transactional_email


def _mock_response(status_code: int, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


def test_send_transactional_email_success():
    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.return_value = _mock_response(201)

    with patch("app.services.brevo_email.httpx.Client", return_value=http_client):
        ok, err = send_transactional_email(
            api_key="xkeysib-secret",
            sender="noreply@example.com",
            recipient="user@example.com",
            subject="Test",
            text_content="hello",
        )

    assert ok is True
    assert err is None


def test_send_transactional_email_api_error():
    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.return_value = _mock_response(401, "Unauthorized")

    with patch("app.services.brevo_email.httpx.Client", return_value=http_client):
        ok, err = send_transactional_email(
            api_key="xkeysib-secret",
            sender="noreply@example.com",
            recipient="user@example.com",
            subject="Test",
            text_content="hello",
        )

    assert ok is False
    assert err == "api_error"


def test_send_transactional_email_retries_transient_status():
    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.side_effect = [
        _mock_response(503, "unavailable"),
        _mock_response(201),
    ]

    with (
        patch("app.services.brevo_email.httpx.Client", return_value=http_client),
        patch("app.services.brevo_email.time.sleep"),
    ):
        ok, err = send_transactional_email(
            api_key="xkeysib-secret",
            sender="noreply@example.com",
            recipient="user@example.com",
            subject="Test",
            text_content="hello",
        )

    assert ok is True
    assert err is None
    assert http_client.post.call_count == 2


def test_send_transactional_email_transport_error():
    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.side_effect = httpx.ConnectError("connection refused")

    with (
        patch("app.services.brevo_email.httpx.Client", return_value=http_client),
        patch("app.services.brevo_email.time.sleep"),
    ):
        ok, err = send_transactional_email(
            api_key="xkeysib-secret",
            sender="noreply@example.com",
            recipient="user@example.com",
            subject="Test",
            text_content="hello",
        )

    assert ok is False
    assert err == "api_transport_error"
    assert http_client.post.call_count == 3
