import os
import subprocess
import sys

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


class ProductionSettingsTests(SimpleTestCase):
    def run_python_with_env(self, code, extra_env=None):
        env = os.environ.copy()
        for key, value in (extra_env or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        env["PYTHONPATH"] = os.getcwd()
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_production_requires_secret_key(self):
        env = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": None,
            "DJANGO_ALLOWED_HOSTS": "app.example.com",
        }
        result = self.run_python_with_env("import django; django.setup()", env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_production_requires_allowed_hosts(self):
        env = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "x" * 64,
            "DJANGO_ALLOWED_HOSTS": "",
        }
        result = self.run_python_with_env("import django; django.setup()", env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_production_secure_defaults(self):
        env = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "x" * 64,
            "DJANGO_ALLOWED_HOSTS": "app.example.com,api.example.com",
        }
        code = """
import django
django.setup()
from django.conf import settings
assert settings.DEBUG is False
assert settings.SECURE_SSL_REDIRECT is True
assert settings.SESSION_COOKIE_SECURE is True
assert settings.SESSION_COOKIE_HTTPONLY is True
assert settings.CSRF_COOKIE_SECURE is True
assert settings.SESSION_COOKIE_SAMESITE in {"Lax", "Strict"}
assert settings.CSRF_COOKIE_SAMESITE in {"Lax", "Strict"}
assert settings.SECURE_HSTS_SECONDS > 0
assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
assert settings.SECURE_HSTS_PRELOAD is True
assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True
assert settings.X_FRAME_OPTIONS == "DENY"
assert settings.SECURE_REFERRER_POLICY
assert settings.CONTENT_SECURITY_POLICY
assert settings.PERMISSIONS_POLICY
assert settings.CORS_ALLOWED_ORIGINS == []
"""
        result = self.run_python_with_env(code, env)

        self.assertEqual(result.returncode, 0, result.stderr)

    @override_settings(
        CORS_ALLOWED_ORIGINS=["https://app.example.com"],
        CONTENT_SECURITY_POLICY="default-src 'self'",
        PERMISSIONS_POLICY="camera=()",
        SECURE_REFERRER_POLICY="no-referrer",
    )
    def test_security_headers_and_cors_are_allowlisted(self):
        client = Client()

        allowed = client.get(reverse("auth-csrf"), HTTP_ORIGIN="https://app.example.com")
        denied = client.get(reverse("auth-csrf"), HTTP_ORIGIN="https://evil.example")

        self.assertEqual(allowed.headers["Access-Control-Allow-Origin"], "https://app.example.com")
        self.assertNotIn("Access-Control-Allow-Origin", denied.headers)
        self.assertEqual(allowed.headers["Content-Security-Policy"], "default-src 'self'")
        self.assertEqual(allowed.headers["Permissions-Policy"], "camera=()")
        self.assertEqual(allowed.headers["Referrer-Policy"], "no-referrer")
