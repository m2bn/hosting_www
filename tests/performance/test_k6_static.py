from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
K6_SCRIPT = ROOT / "tests" / "performance" / "k6" / "staging.load.js"
K6_FIXTURE = ROOT / "tests" / "performance" / "k6" / "static-site.zip.base64"
LOAD_TEST_RUNBOOK = ROOT / "docs" / "runbooks" / "load-testing.md"


class K6LoadTestStaticTests(TestCase):
    def test_k6_script_defines_required_scenarios(self):
        script = K6_SCRIPT.read_text(encoding="utf-8")

        for scenario in [
            "login",
            "projects_list",
            "static_upload",
            "deployment",
            "stripe_webhook",
            "deployment_logs",
            "dashboard",
            "api_rate_limit",
        ]:
            with self.subTest(scenario=scenario):
                self.assertIn(f"{scenario}:", script)

    def test_k6_script_has_acceptance_thresholds(self):
        script = K6_SCRIPT.read_text(encoding="utf-8")

        for threshold in ["http_req_failed", "p(95)<750", "p(95)<5000", "rate>0.95"]:
            with self.subTest(threshold=threshold):
                self.assertIn(threshold, script)

    def test_k6_script_refuses_production_targets(self):
        script = K6_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("LOAD_TEST_ENV=staging", script)
        self.assertIn("production-looking URL", script)
        self.assertIn("api.example.com", script)
        self.assertIn("app.example.com", script)

    def test_static_upload_fixture_exists_without_plaintext_secrets(self):
        fixture = K6_FIXTURE.read_text(encoding="utf-8").strip()

        self.assertGreater(len(fixture), 100)
        self.assertNotIn("secret", fixture.lower())
        self.assertNotIn("password", fixture.lower())

    def test_runbook_documents_staging_execution_and_no_production(self):
        runbook = LOAD_TEST_RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("staging", runbook.lower())
        self.assertIn("Nie uruchamiaj", runbook)
        self.assertIn("production", runbook.lower())
        self.assertIn("progi akceptacji", runbook.lower())
