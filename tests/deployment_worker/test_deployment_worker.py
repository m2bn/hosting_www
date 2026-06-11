import logging
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


SERVICE_ROOT = Path(__file__).resolve().parents[2] / "apps" / "deployment-worker"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from deployment_worker import tasks
from deployment_worker.adapters import ArtifactScanner, ContainerBuilder, StaticSiteBuilder
from deployment_worker.backoff import retry_countdown
from deployment_worker.repository import repository
from deployment_worker.statuses import BuildJobStatus, DeploymentStatus
from deployment_worker.structured_logging import JsonFormatter


class DeploymentWorkerTests(TestCase):
    def setUp(self):
        repository.clear()
        self.payload = {
            "request_id": "req-123",
            "correlation_id": "corr-123",
            "organization_public_id": "org-123",
            "project_public_id": "project-123",
            "environment_public_id": "env-123",
            "project_slug": "website",
            "build_job_public_id": "build-123",
            "deployment_public_id": "deploy-123",
            "kubernetes_namespace": "proj-website",
            "workload_name": "runtime",
            "image_ref": "registry.example.com/private/website:deploy-123",
            "image_digest": "sha256:deploy-123",
        }

    def test_create_static_deployment_updates_build_and_deployment_statuses(self):
        result = tasks.create_static_deployment.run(self.payload)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(repository.build_jobs["build-123"]["status"], BuildJobStatus.SUCCEEDED)
        self.assertEqual(repository.deployments["deploy-123"]["status"], DeploymentStatus.SCANNING)
        self.assertTrue(any(event.event_type == "build_job.succeeded" for event in repository.events))

    def test_create_container_deployment_records_image_metadata(self):
        result = tasks.create_container_deployment.run(self.payload)

        self.assertEqual(result["status"], "succeeded")
        deployment = repository.deployments["deploy-123"]
        self.assertEqual(deployment["status"], DeploymentStatus.SCANNING)
        self.assertIn("image_ref", deployment)
        self.assertIn("image_digest", deployment)

    def test_scan_artifact_moves_deployment_to_deploying(self):
        result = tasks.scan_artifact.run(self.payload)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(repository.deployments["deploy-123"]["status"], DeploymentStatus.DEPLOYING)
        self.assertTrue(any(event.event_type == "deployment.scan_passed" for event in repository.events))

    def test_scan_artifact_blocks_when_policy_fails(self):
        with patch.object(ArtifactScanner, "scan", return_value={"decision": "block"}):
            result = tasks.scan_artifact.run(self.payload)

        self.assertEqual(result["status"], "failed_terminal")
        self.assertEqual(result["error_code"], "policy_blocked")
        self.assertEqual(repository.deployments["deploy-123"]["status"], DeploymentStatus.FAILED)

    def test_deploy_to_runtime_marks_deployment_active(self):
        result = tasks.deploy_to_runtime.run(self.payload)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(repository.deployments["deploy-123"]["status"], DeploymentStatus.ACTIVE)
        self.assertTrue(any(event.event_type == "deployment.active" for event in repository.events))

    def test_rollback_deployment_marks_deployment_rolled_back(self):
        payload = {**self.payload, "target_deployment_public_id": "deploy-previous"}

        result = tasks.rollback_deployment.run(payload)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(repository.deployments["deploy-123"]["status"], DeploymentStatus.ROLLED_BACK)
        self.assertTrue(any(event.event_type == "deployment.rolled_back" for event in repository.events))

    def test_control_plane_secret_fields_are_blocked(self):
        payload = {**self.payload, "stripe_secret_key": "sk_live_should_not_be_here"}

        result = tasks.create_static_deployment.run(payload)

        self.assertEqual(result["status"], "failed_terminal")
        self.assertEqual(result["error_code"], "policy_blocked")

    def test_artifact_size_limits_are_enforced(self):
        oversized = {"artifact_ref": "artifact", "logs_ref": "logs", "checksum": "sha256:x", "size_bytes": 10**12}
        with patch.object(StaticSiteBuilder, "build", return_value=oversized):
            result = tasks.create_static_deployment.run(self.payload)

        self.assertEqual(result["status"], "failed_terminal")
        self.assertEqual(result["error_code"], "policy_blocked")

    def test_container_image_size_limits_are_enforced(self):
        oversized = {"image_ref": "image", "image_digest": "sha256:x", "logs_ref": "logs", "size_bytes": 10**12}
        with patch.object(ContainerBuilder, "build", return_value=oversized):
            result = tasks.create_container_deployment.run(self.payload)

        self.assertEqual(result["status"], "failed_terminal")
        self.assertEqual(result["error_code"], "policy_blocked")

    def test_retry_backoff_is_exponential_and_capped(self):
        self.assertGreaterEqual(retry_countdown(2, jitter=False), retry_countdown(1, jitter=False))
        self.assertLessEqual(retry_countdown(20, jitter=False), 900)

    def test_structured_logs_include_correlation_id(self):
        record = logging.LogRecord(
            name="deployment",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="task",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "corr-123"
        record.deployment_public_id = "deploy-123"
        record.operation = "deploy_to_runtime"

        output = JsonFormatter().format(record)

        self.assertIn('"correlation_id": "corr-123"', output)
        self.assertIn('"deployment_public_id": "deploy-123"', output)
        self.assertIn('"operation": "deploy_to_runtime"', output)
