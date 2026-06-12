from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


SECURITY_COVERAGE = {
    "IDOR": ("tests/security/test_idor.py", ["cannot_retrieve_tenant_b_project", "cannot_update_tenant_b_project"]),
    "CSRF": ("apps/api/tests_authentication.py", ["test_csrf_is_required_for_session_login_endpoint"]),
    "brute force login": ("apps/api/tests_authentication.py", ["test_brute_force_rate_limit_blocks_repeated_failed_logins"]),
    "rate limiting": ("apps/api/tests_api_keys.py", ["rate_limit"]),
    "invalid Stripe webhook signature": ("apps/api/tests_stripe_webhooks.py", ["test_invalid_signature_is_rejected", "test_missing_signature_is_rejected"]),
    "duplicate Stripe webhook": ("apps/api/tests_stripe_webhooks.py", ["test_duplicate_webhook_is_idempotent"]),
    "replay webhook": ("apps/api/tests_stripe_webhooks.py", ["test_replay_webhook_returns_ok_without_second_state_change"]),
    "zip slip": ("apps/api/tests_static_deployments.py", ["test_zip_slip_is_rejected"]),
    "symlink upload": ("apps/api/tests_static_deployments.py", ["test_symlink_is_rejected"]),
    "unauthorized organization access": ("apps/api/tests_organizations.py", ["test_user_outside_organization_has_no_access"]),
    "API key scope bypass": ("apps/api/tests_api_keys.py", ["scope", "another_project", "another_organization"]),
    "secret leakage in logs": ("apps/api/tests_secrets.py", ["test_secret_values_do_not_appear_in_application_logs"]),
    "SSRF prevention": ("tests/security/test_ssrf_and_private_resource_guards.py", ["test_upload_and_deployment_modules_do_not_perform_direct_url_fetches"]),
    "domain takeover": ("apps/api/tests_custom_domains.py", ["test_pending_domain_takeover_attempt_is_blocked", "test_domain_assigned_to_other_organization_is_blocked"]),
    "privilege escalation in RBAC": ("apps/api/tests_authorization.py", ["viewer", "billing", "developer"]),
    "Kubernetes manifest policy validation": ("tests/security/test_kubernetes_manifest_policy_validation.py", ["test_runtime_policy_blocks_dangerous_pod_settings"]),
    "insecure headers": ("tests/security/test_platform_security_configuration.py", ["test_security_headers_are_present"]),
    "CORS misconfiguration": ("tests/security/test_platform_security_configuration.py", ["test_cors_is_allowlist_based"]),
    "public access to private resources": ("apps/api/tests_secrets.py", ["test_secret_from_project_a_is_not_accessible_through_project_b"]),
    "missing audit logs for critical actions": ("tests/security/test_audit_coverage.py", ["test_critical_api_tests_assert_audit_logs"]),
}


class SecurityCoverageMatrixTests(TestCase):
    """Keeps the explicit security-test catalog wired to concrete test files."""

    def test_required_security_scenarios_have_named_regression_tests(self):
        for scenario, (relative_path, required_markers) in SECURITY_COVERAGE.items():
            with self.subTest(scenario=scenario):
                path = ROOT / relative_path
                self.assertTrue(path.exists(), f"{scenario} test file is missing: {relative_path}")
                content = path.read_text(encoding="utf-8")
                for marker in required_markers:
                    self.assertIn(marker, content, f"{scenario} coverage marker is missing: {marker}")

    def test_ci_runs_security_catalog(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Run security test suite", workflow)
        self.assertIn("python manage.py test", workflow)
        self.assertIn("tests.security", workflow)
        for module in [
            "apps.api.tests_authentication",
            "apps.api.tests_api_keys",
            "apps.api.tests_stripe_webhooks",
            "apps.api.tests_static_deployments",
            "apps.api.tests_custom_domains",
            "apps.api.tests_secrets",
            "apps.api.tests_organizations",
        ]:
            with self.subTest(module=module):
                self.assertIn(module, workflow)
