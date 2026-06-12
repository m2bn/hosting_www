from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class AuditCoverageTests(TestCase):
    """Checks that critical action tests assert AuditLog behavior, not only HTTP success."""

    def test_critical_api_tests_assert_audit_logs(self):
        expected_files = [
            "apps/api/tests_authentication.py",
            "apps/api/tests_organizations.py",
            "apps/api/tests_projects.py",
            "apps/api/tests_static_deployments.py",
            "apps/api/tests_custom_domains.py",
            "apps/api/tests_billing_checkout.py",
            "apps/api/tests_stripe_webhooks.py",
            "apps/api/tests_api_keys.py",
            "apps/api/tests_secrets.py",
        ]

        for relative_path in expected_files:
            with self.subTest(file=relative_path):
                content = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("AuditLog", content)
                self.assertIn("Audit", content)
