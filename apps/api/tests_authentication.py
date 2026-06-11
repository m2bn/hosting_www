import json

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.api.auth_utils import totp_code
from apps.api.models import (
    AuditLog,
    AuthToken,
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    Role,
    RoleScope,
    TwoFactorRecoveryCode,
    TwoFactorDevice,
    User,
)
from apps.api.rbac import ROLE_OWNER


class SessionAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            email="user@example.com",
            password="correct-password",
            is_email_verified=True,
        )

    def csrf(self, client=None):
        client = client or self.client
        client.get(reverse("auth-csrf"))
        return client.cookies["csrftoken"].value

    def post_json(self, path_name, payload, client=None):
        client = client or self.client
        return client.post(
            reverse(path_name),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(client),
        )

    def test_correct_login_creates_session_cookie_and_current_user_endpoint_works(self):
        response = self.post_json(
            "auth-login",
            {"email": "user@example.com", "password": "correct-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", response.cookies)
        self.assertTrue(response.cookies["sessionid"]["httponly"])

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        self.assertTrue(AuditLog.objects.filter(action="auth.login.succeeded").exists())

    def test_wrong_login_is_rejected_and_audited(self):
        response = self.post_json(
            "auth-login",
            {"email": "user@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sessionid", response.cookies)
        self.assertTrue(AuditLog.objects.filter(action="auth.login.failed").exists())

    def test_brute_force_rate_limit_blocks_repeated_failed_logins(self):
        for _ in range(5):
            response = self.post_json(
                "auth-login",
                {"email": "user@example.com", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 400)

        response = self.post_json(
            "auth-login",
            {"email": "user@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_csrf_is_required_for_session_login_endpoint(self):
        response = self.client.post(
            reverse("auth-login"),
            data={"email": "user@example.com", "password": "correct-password"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_password_reset_request_does_not_reveal_whether_account_exists(self):
        existing = self.post_json("auth-password-reset", {"email": "user@example.com"})
        missing = self.post_json("auth-password-reset", {"email": "missing@example.com"})

        self.assertEqual(existing.status_code, 200)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(existing.json(), missing.json())
        self.assertEqual(AuthToken.objects.count(), 1)

    def test_owner_login_requires_2fa_setup(self):
        owner = User.objects.create_user(email="owner@example.com", password="owner-password")
        role = Role.objects.create(scope=RoleScope.ORGANIZATION, key=ROLE_OWNER, name="Owner")
        org = Organization.objects.create(name="Acme", slug="acme", owner_user=owner)
        OrganizationMember.objects.create(
            organization=org,
            user=owner,
            role=role,
            status=OrganizationMemberStatus.ACTIVE,
        )

        response = self.post_json(
            "auth-login",
            {"email": "owner@example.com", "password": "owner-password"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "2fa_setup_required")

    def test_2fa_recovery_codes_are_hashed_and_can_be_used_once(self):
        self.client.force_login(self.user)
        setup_response = self.post_json("auth-2fa-setup", {})
        secret = setup_response.json()["secret"]
        device = TwoFactorDevice.objects.get(user=self.user)
        self.assertNotEqual(device.secret, secret)

        enable_response = self.post_json("auth-2fa-enable", {"totp": totp_code(secret)})

        self.assertEqual(enable_response.status_code, 200)
        raw_code = enable_response.json()["recovery_codes"][0]
        stored_code = TwoFactorRecoveryCode.objects.first()
        self.assertNotEqual(stored_code.code_hash, raw_code)
        self.assertTrue(stored_code.check_code(raw_code))

    def test_password_change_invalidates_current_session(self):
        self.post_json("auth-login", {"email": "user@example.com", "password": "correct-password"})
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

        response = self.post_json(
            "auth-password-change",
            {"current_password": "correct-password", "new_password": "new-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Strict")
    def test_session_cookie_has_secure_parameters_in_production_settings(self):
        client = Client(enforce_csrf_checks=True)
        response = self.post_json(
            "auth-login",
            {"email": "user@example.com", "password": "correct-password"},
            client=client,
        )

        self.assertEqual(response.status_code, 200)
        session_cookie = response.cookies["sessionid"]
        self.assertTrue(session_cookie["httponly"])
        self.assertTrue(session_cookie["secure"])
        self.assertEqual(session_cookie["samesite"], "Strict")


class RegistrationAndVerificationTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def csrf(self):
        self.client.get(reverse("auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def test_registration_and_email_verification(self):
        response = self.client.post(
            reverse("auth-register"),
            data=json.dumps({"email": "new@example.com", "password": "safe-password", "full_name": "New User"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 201)
        token = response.json()["email_verification_token"]

        response = self.client.post(
            reverse("auth-email-verify"),
            data=json.dumps({"token": token}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.is_email_verified)
        self.assertTrue(AuditLog.objects.filter(action="auth.email_verified").exists())
