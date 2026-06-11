import json
import logging
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api.models import AuditLog, AuthToken, NotificationMessage, NotificationStatus, User
from apps.api.notifications import (
    EmailClient,
    NotificationRateLimited,
    enqueue_notification,
    process_notification,
    send_email_verification,
    send_password_reset,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATION_RATE_LIMIT_ATTEMPTS=2,
    NOTIFICATION_RATE_LIMIT_WINDOW_SECONDS=3600,
    NOTIFICATION_BASE_URL="https://app.example.test",
)
class NotificationServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(email="user@example.com", password="secret")

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def test_verification_email_is_sent_and_token_is_not_stored_in_notification_context(self):
        response = self.client.post(
            reverse("auth-register"),
            data=json.dumps({"email": "new@example.com", "password": "safe-password"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 201)
        token = response.json()["email_verification_token"]
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(token, mail.outbox[0].body)
        message = NotificationMessage.objects.get(event_type="email_verification")
        self.assertEqual(message.status, NotificationStatus.SENT)
        self.assertNotIn(token, json.dumps(message.context))
        self.assertEqual(AuthToken.objects.count(), 1)
        self.assertNotEqual(AuthToken.objects.get().token_hash, token)

    def test_password_reset_email_does_not_reveal_account_and_sends_for_existing_user(self):
        existing = self.client.post(
            reverse("auth-password-reset"),
            data=json.dumps({"email": "user@example.com"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        missing = self.client.post(
            reverse("auth-password-reset"),
            data=json.dumps({"email": "missing@example.com"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(existing.status_code, 200)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(existing.json(), missing.json())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(NotificationMessage.objects.filter(event_type="password_reset").count(), 1)

    def test_retry_after_email_backend_error(self):
        message = enqueue_notification(event_type="deployment_succeeded", recipient_email="user@example.com", context={"deployment_id": "dep", "project_name": "app"})

        with patch.object(EmailClient, "send", side_effect=RuntimeError("smtp down")):
            process_notification(message)

        message.refresh_from_db()
        self.assertEqual(message.status, NotificationStatus.QUEUED)
        self.assertEqual(message.attempts, 1)

        with patch.object(EmailClient, "send", return_value=1):
            process_notification(message)

        message.refresh_from_db()
        self.assertEqual(message.status, NotificationStatus.SENT)
        self.assertEqual(message.attempts, 2)

    def test_token_is_not_logged_on_send_failure(self):
        raw_token = "reset-token-super-secret"
        logger = logging.getLogger("apps.api.notifications")

        with self.assertLogs(logger, level="WARNING") as captured:
            with patch.object(EmailClient, "send", side_effect=RuntimeError("smtp token leak attempt")):
                send_password_reset(self.user, raw_token)

        logs = "\n".join(captured.output)
        self.assertNotIn(raw_token, logs)
        self.assertNotIn(raw_token, json.dumps(list(NotificationMessage.objects.values_list("context", flat=True))))

    def test_rate_limiting_blocks_excessive_email_sends(self):
        enqueue_notification(event_type="domain_verified", recipient_email="user@example.com", context={"domain": "a.example"}, send_now=False)
        enqueue_notification(event_type="domain_verified", recipient_email="user@example.com", context={"domain": "b.example"}, send_now=False)

        with self.assertRaises(NotificationRateLimited):
            enqueue_notification(event_type="domain_verified", recipient_email="user@example.com", context={"domain": "c.example"}, send_now=False)

        self.assertEqual(NotificationMessage.objects.filter(status=NotificationStatus.RATE_LIMITED).count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="notification.rate_limited").exists())

    def test_critical_notification_is_audited_after_send(self):
        enqueue_notification(event_type="payment_failed", recipient_email="user@example.com", context={"organization_name": "Acme"}, send_now=True)

        self.assertTrue(AuditLog.objects.filter(action="notification.sent").exists())

    def test_direct_email_verification_helper_sends_mail(self):
        send_email_verification(self.user, "verify-token")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-token", mail.outbox[0].body)
