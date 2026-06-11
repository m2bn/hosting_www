import logging
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch


SERVICE_ROOT = Path(__file__).resolve().parents[2] / "apps" / "provisioner-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from provisioner_service import tasks
from provisioner_service.backoff import retry_countdown
from provisioner_service.idempotency import store
from provisioner_service.k8s import KubernetesProvisioner, ProjectRef
from provisioner_service.structured_logging import JsonFormatter


class ProvisionerServiceTests(TestCase):
    def setUp(self):
        store.clear()
        self.payload = {
            "request_id": "req-123",
            "correlation_id": "corr-123",
            "job_id": "job-123",
            "organization_public_id": "org-123",
            "project_public_id": "project-123",
            "environment_public_id": "env-123",
            "project_slug": "website",
            "environment_slug": "production",
            "quotas": {"requests.cpu": "1", "limits.memory": "1Gi"},
            "limits": {"default": {"cpu": "500m", "memory": "512Mi"}},
        }

    def task_run(self, task, payload):
        return task.run(payload)

    def test_provision_project_creates_expected_kubernetes_resources(self):
        client = Mock()
        with patch("provisioner_service.tasks.KubernetesProvisioner", return_value=client):
            result = self.task_run(tasks.provision_project, self.payload)

        self.assertEqual(result["status"], "succeeded")
        client.provision_project.assert_called_once()
        ref = client.provision_project.call_args.args[0]
        self.assertEqual(ref.namespace, "proj-website-project")

    def test_duplicate_task_is_idempotent(self):
        client = Mock()
        with patch("provisioner_service.tasks.KubernetesProvisioner", return_value=client):
            first = self.task_run(tasks.provision_project, self.payload)
            second = self.task_run(tasks.provision_project, self.payload)

        self.assertEqual(first["status"], "succeeded")
        self.assertTrue(second["idempotent"])
        client.provision_project.assert_called_once()

    def test_deprovision_project_deletes_project_resources(self):
        client = Mock()
        with patch("provisioner_service.tasks.KubernetesProvisioner", return_value=client):
            result = self.task_run(tasks.deprovision_project, self.payload)

        self.assertEqual(result["status"], "succeeded")
        client.deprovision_project.assert_called_once()

    def test_domain_and_certificate_tasks_call_expected_client_methods(self):
        payload = {**self.payload, "domain_public_id": "domain-12345678", "hostname": "app.example.com"}
        client = Mock()
        with patch("provisioner_service.tasks.KubernetesProvisioner", return_value=client):
            tasks.provision_domain.run(payload)
            tasks.deprovision_domain.run({**payload, "idempotency_key": "domain.deprovision:domain-12345678"})
            tasks.provision_certificate.run({**payload, "idempotency_key": "certificate.provision:domain-12345678"})

        client.provision_domain.assert_called_once()
        client.deprovision_domain.assert_called_once()
        client.provision_certificate.assert_called_once()

    def test_kubernetes_client_builds_minimal_resources(self):
        core = Mock()
        networking = Mock()
        custom = Mock()
        ref = ProjectRef(
            organization_public_id="org-123",
            project_public_id="project-123",
            environment_public_id="env-123",
            project_slug="website",
        )

        KubernetesProvisioner(core_v1=core, networking_v1=networking, custom_objects=custom).provision_project(ref)

        core.create_namespace.assert_called_once()
        core.create_namespaced_service_account.assert_called_once()
        core.create_namespaced_resource_quota.assert_called_once()
        core.create_namespaced_limit_range.assert_called_once()
        networking.create_namespaced_network_policy.assert_called_once()
        namespace_body = core.create_namespace.call_args.kwargs["body"]
        self.assertEqual(namespace_body["metadata"]["labels"]["managed_by"], "provisioner")
        self.assertEqual(namespace_body["metadata"]["labels"]["project_public_id"], "project-123")

    def test_kubernetes_client_ignores_already_exists_and_not_found(self):
        already_exists = Exception("already exists")
        already_exists.status = 409
        not_found = Exception("not found")
        not_found.status = 404
        core = Mock()
        networking = Mock()
        custom = Mock()
        core.create_namespace.side_effect = already_exists
        core.delete_namespace.side_effect = not_found
        ref = ProjectRef("org-123", "project-123", "env-123", "website")
        client = KubernetesProvisioner(core_v1=core, networking_v1=networking, custom_objects=custom)

        client.ensure_namespace(ref)
        client.delete_namespace(ref)

        core.create_namespace.assert_called_once()
        core.delete_namespace.assert_called_once()

    def test_retry_backoff_is_exponential_with_cap(self):
        self.assertGreaterEqual(retry_countdown(2, jitter=False), retry_countdown(1, jitter=False))
        self.assertLessEqual(retry_countdown(20, jitter=False), 1800)

    def test_structured_logs_include_correlation_fields(self):
        record = logging.LogRecord(
            name="provisioner",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="job",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-123"
        record.correlation_id = "corr-123"
        record.operation = "project.provision"

        output = JsonFormatter().format(record)

        self.assertIn('"request_id": "req-123"', output)
        self.assertIn('"correlation_id": "corr-123"', output)
        self.assertIn('"operation": "project.provision"', output)
