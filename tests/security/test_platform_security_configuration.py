from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


class PlatformSecurityConfigurationTests(SimpleTestCase):
    """Regression tests for browser-facing headers and CORS allowlisting."""

    @override_settings(
        CONTENT_SECURITY_POLICY="default-src 'self'; object-src 'none'",
        PERMISSIONS_POLICY="camera=(), microphone=(), geolocation=()",
        SECURE_REFERRER_POLICY="strict-origin-when-cross-origin",
        CORS_ALLOWED_ORIGINS=["https://app.example.test"],
    )
    def test_security_headers_are_present(self):
        response = Client().get(reverse("auth-csrf"))

        self.assertEqual(response.headers["Content-Security-Policy"], "default-src 'self'; object-src 'none'")
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    @override_settings(CORS_ALLOWED_ORIGINS=["https://app.example.test"])
    def test_cors_is_allowlist_based(self):
        client = Client()

        allowed = client.options(reverse("auth-csrf"), HTTP_ORIGIN="https://app.example.test")
        denied = client.options(reverse("auth-csrf"), HTTP_ORIGIN="https://evil.example.test")

        self.assertEqual(allowed.headers["Access-Control-Allow-Origin"], "https://app.example.test")
        self.assertEqual(allowed.headers["Access-Control-Allow-Credentials"], "true")
        self.assertNotIn("Access-Control-Allow-Origin", denied.headers)
        self.assertNotIn("Access-Control-Allow-Credentials", denied.headers)
