import sys
import tempfile
from pathlib import Path
from unittest import TestCase


SERVICE_ROOT = Path(__file__).resolve().parents[2] / "apps" / "deployment-worker"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from deployment_worker.container_pipeline import (
    BuildContext,
    BuildLimits,
    BuildStrategy,
    BuildpackStrategy,
    DockerfileBuildStrategy,
    ImageScanResult,
    ImageScanStep,
    RollbackStep,
    RuntimeDeployStep,
)
from deployment_worker.errors import PolicyBlockedError
from deployment_worker.statuses import ContainerBuildStatus


class ContainerPipelineInterfaceTests(TestCase):
    def setUp(self):
        self.payload = {
            "project_slug": "website",
            "deployment_public_id": "deploy-123",
            "build_job_public_id": "build-123",
            "kubernetes_namespace": "proj-website",
            "workload_name": "runtime",
            "image_ref": "registry.example.com/private/website:deploy-123",
            "image_digest": "sha256:deploy-123",
        }

    def test_build_strategy_is_an_interface(self):
        with self.assertRaises(TypeError):
            BuildStrategy()

    def test_dockerfile_strategy_builds_private_image_and_user_logs_ref(self):
        context = BuildContext.from_payload(self.payload)

        result = DockerfileBuildStrategy().build(context)

        self.assertEqual(result.status, ContainerBuildStatus.READY_FOR_DEPLOY)
        self.assertTrue(result.image_ref.startswith("registry.example.com/private/website:"))
        self.assertEqual(result.logs_ref, "logs/build/build-123.log")

    def test_dockerignore_is_respected_when_calculating_context_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("FROM nginx\n", encoding="utf-8")
            (root / ".dockerignore").write_text("node_modules/\n", encoding="utf-8")
            (root / "index.html").write_text("ok", encoding="utf-8")
            ignored = root / "node_modules"
            ignored.mkdir()
            (ignored / "large.bin").write_bytes(b"x" * 1024)
            context = BuildContext(
                root=root,
                project_slug="website",
                deployment_public_id="deploy-123",
                build_job_public_id="build-123",
                limits=BuildLimits(max_context_bytes=64),
            )

            result = DockerfileBuildStrategy().build(context)

            self.assertLessEqual(result.size_bytes, 64)

    def test_build_context_size_limit_blocks_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("FROM nginx\n", encoding="utf-8")
            (root / "large.bin").write_bytes(b"x" * 128)
            context = BuildContext(
                root=root,
                project_slug="website",
                deployment_public_id="deploy-123",
                build_job_public_id="build-123",
                limits=BuildLimits(max_context_bytes=32),
            )

            with self.assertRaises(PolicyBlockedError):
                DockerfileBuildStrategy().build(context)

    def test_symlink_in_build_context_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("FROM nginx\n", encoding="utf-8")
            target = root / "target.txt"
            target.write_text("secret", encoding="utf-8")
            try:
                (root / "link.txt").symlink_to(target)
            except OSError:
                self.skipTest("Symlinks are not available in this environment.")

            context = BuildContext(
                root=root,
                project_slug="website",
                deployment_public_id="deploy-123",
                build_job_public_id="build-123",
            )

            with self.assertRaises(PolicyBlockedError):
                DockerfileBuildStrategy().build(context)

    def test_build_pod_spec_is_isolated_and_unprivileged(self):
        context = BuildContext.from_payload(self.payload)

        spec = DockerfileBuildStrategy().build_pod_spec(context)

        container = spec["containers"][0]
        self.assertTrue(spec["namespace"].startswith("build-website-"))
        self.assertFalse(spec["automountServiceAccountToken"])
        self.assertEqual(spec["volumes"], [])
        self.assertFalse(container["securityContext"]["privileged"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertTrue(container["securityContext"]["runAsNonRoot"])
        self.assertIn("limits", container["resources"])
        self.assertEqual(container["env"], [])

    def test_buildpack_strategy_is_placeholder(self):
        context = BuildContext.from_payload(self.payload)

        with self.assertRaises(NotImplementedError):
            BuildpackStrategy().build(context)

    def test_image_scan_blocks_critical_vulnerabilities(self):
        result = ImageScanResult(
            scan_report_ref="scans/deploy-123.json",
            sbom_ref="sbom/deploy-123.json",
            decision="pass",
            critical_count=1,
        )

        with self.assertRaises(PolicyBlockedError):
            ImageScanStep().evaluate(result)

    def test_runtime_deploy_requires_scanned_image_and_project_namespace(self):
        result = RuntimeDeployStep().deploy(self.payload)

        spec = result["spec"]
        self.assertEqual(result["namespace"], "proj-website")
        self.assertTrue(spec["networkPolicyRequired"])
        self.assertIn("readinessProbe", spec)
        self.assertIn("livenessProbe", spec)
        self.assertFalse(spec["securityContext"]["privileged"])
        self.assertIn("limits", spec["resources"])

    def test_runtime_deploy_without_image_digest_is_blocked(self):
        payload = {**self.payload, "image_digest": ""}

        with self.assertRaises(PolicyBlockedError):
            RuntimeDeployStep().deploy(payload)

    def test_rollback_requires_target_deployment(self):
        payload = {**self.payload, "target_deployment_public_id": "deploy-previous"}

        result = RollbackStep().rollback(payload)

        self.assertEqual(result["rolled_back_to"], "deploy-previous")
        self.assertEqual(result["namespace"], "proj-website")
