from unittest.mock import MagicMock, patch

import httpx
import pytest
import smtplib

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
    monkeypatch.setattr(settings, "email_backend", "brevo_api")
    monkeypatch.setattr(settings, "smtp_from", "   ")
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-secret")

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

    smtp_ctor.assert_called_once_with("mailhog", 1025, timeout=5.0)
    smtp_instance.send_message.assert_called_once()


def test_send_login_code_brevo_api_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "email_backend", "brevo_api")
    monkeypatch.setattr(settings, "smtp_from", "noreply@yourdomain.com")
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-secret")

    with patch(
        "app.services.email_delivery.send_transactional_email",
        return_value=(True, None),
    ) as send_api:
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is True
        assert err is None

    send_api.assert_called_once_with(
        api_key="xkeysib-secret",
        sender="noreply@yourdomain.com",
        recipient="111550073@nycu.edu.tw",
        subject="Your Active Defense login code",
        text_content="Your verification code is: 123456",
    )


def test_send_login_code_brevo_api_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "email_backend", "brevo_api")
    monkeypatch.setattr(settings, "brevo_api_key", "")

    service = EmailDeliveryService()
    ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
    assert ok is False
    assert err == "missing_api_key"


def test_send_login_code_smtp_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "noreply@yourdomain.com")
    monkeypatch.setattr(settings, "smtp_user", "you@example.com")
    monkeypatch.setattr(settings, "smtp_password", "xsmtpsib-secret")
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)

    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_delivery.smtplib.SMTP", return_value=smtp_instance) as smtp_ctor:
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is True
        assert err is None

    smtp_ctor.assert_called_once_with("smtp-relay.brevo.com", 587, timeout=15.0)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("you@example.com", "xsmtpsib-secret")
    smtp_instance.send_message.assert_called_once()


def test_send_login_code_smtp_refuses_brevo_without_tls(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 1025)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)

    with patch("app.services.email_delivery.smtplib.SMTP") as smtp_ctor:
        service = EmailDeliveryService()
        ok, err = service.send_login_code("111550073@nycu.edu.tw", "123456")
        assert ok is False
        assert err == "tls_required"

    smtp_ctor.assert_not_called()


def test_send_login_code_smtp_auth_failure(monkeypatch):
    monkeypatch.setattr(settings, "app_debug", False)
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp-relay.brevo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "user")
    monkeypatch.setattr(settings, "smtp_password", "bad")
    monkeypatch.setattr(settings, "smtp_use_tls", True)

    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)
    smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

    with patch("app.services.email_delivery.smtplib.SMTP", return_value=smtp_instance):
        service = EmailDeliveryService()
        ok, err = service.send_login_code("demo1@active-defense.local", "123456")
        assert ok is False
        assert err == "smtp_auth_failed"


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

    smtp_ctor.assert_called_once_with("mailhog", 1025, timeout=5.0)
