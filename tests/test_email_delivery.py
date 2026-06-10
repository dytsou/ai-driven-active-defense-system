from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.email_delivery import EmailDeliveryService, mask_email


def test_mask_email_nycu_student_id():
    assert mask_email("111550073@nycu.edu.tw") == "111***073@nycu.edu.tw"


def test_mask_email_short_local_part():
    assert mask_email("ab@example.com") == "a***b@example.com"


def test_send_login_code_rejects_empty_recipient():
    service = EmailDeliveryService()
    ok, err = service.send_login_code("", "123456")
    assert ok is False
    assert err == "missing_recipient"


def test_send_login_code_rejects_missing_from(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "smtp_from", "   ")
    monkeypatch.setattr(settings, "smtp_password", "xkeysib-secret")

    service = EmailDeliveryService()
    ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
    assert ok is False
    assert err == "missing_from"


def test_send_login_code_mailhog_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)

    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_delivery.smtplib.SMTP", return_value=smtp_instance) as smtp_ctor:
        service = EmailDeliveryService()
        ok, err = service.send_login_code("demo1@active-defense.local", "654321")
        assert ok is True
        assert err is None

    smtp_ctor.assert_called_once_with("mailhog", 1025, timeout=5)
    smtp_instance.send_message.assert_called_once()


def test_send_login_code_brevo_api_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "noreply@yourdomain.com")
    monkeypatch.setattr(settings, "smtp_password", "xkeysib-secret")

    response = MagicMock()
    response.status_code = 201

    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.return_value = response

    with patch("app.services.email_delivery.httpx.Client", return_value=http_client):
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is True
        assert err is None

    http_client.post.assert_called_once()
    _, kwargs = http_client.post.call_args
    assert kwargs["json"]["sender"]["email"] == "noreply@yourdomain.com"
    assert kwargs["json"]["to"] == [{"email": "111550073@nycu.edu.tw"}]
    assert kwargs["headers"]["api-key"] == "xkeysib-secret"


def test_send_login_code_brevo_api_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "smtp_password", "")

    service = EmailDeliveryService()
    ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
    assert ok is False
    assert err == "smtp_auth_failed"


def test_send_login_code_brevo_api_error_response(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "smtp_from", "noreply@yourdomain.com")
    monkeypatch.setattr(settings, "smtp_password", "xkeysib-secret")

    response = MagicMock()
    response.status_code = 401
    response.text = "Unauthorized"

    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.return_value = response

    with patch("app.services.email_delivery.httpx.Client", return_value=http_client):
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is False
        assert err == "api_error"


def test_send_login_code_brevo_api_transport_failure(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "smtp_from", "noreply@yourdomain.com")
    monkeypatch.setattr(settings, "smtp_password", "xkeysib-secret")

    http_client = MagicMock()
    http_client.__enter__ = MagicMock(return_value=http_client)
    http_client.__exit__ = MagicMock(return_value=False)
    http_client.post.side_effect = httpx.ConnectError("connection refused")

    with patch("app.services.email_delivery.httpx.Client", return_value=http_client):
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is False
        assert err == "smtp_error"


def test_send_login_code_local_smtp_failure(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", True)

    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)
    smtp_instance.send_message.side_effect = OSError("mailhog down")

    with patch("app.services.email_delivery.smtplib.SMTP", return_value=smtp_instance):
        service = EmailDeliveryService()
        ok, err = service.send_login_code("demo1@active-defense.local", "123456")
        assert ok is False
        assert err == "smtp_error"


def test_app_debug_overrides_production_smtp(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)

    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_delivery.smtplib.SMTP", return_value=smtp_instance) as smtp_ctor:
        service = EmailDeliveryService()
        ok, err = service.send_login_code("demo1@active-defense.local", "123456")
        assert ok is True
        assert err is None

    smtp_ctor.assert_called_once_with("mailhog", 1025, timeout=5)
