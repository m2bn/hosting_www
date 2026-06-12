from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_POLICY = ROOT / "infra" / "policies" / "kyverno-runtime-baseline.yaml"
RUNTIME_MANIFEST = ROOT / "infra" / "kubernetes" / "customer-runtime-baseline.yaml"
PLATFORM_CHART = ROOT / "infra" / "helm" / "platform-services"


class KubernetesManifestPolicyValidationTests(TestCase):
    """Static validation for Kubernetes and Helm security controls used by CI."""

    def test_runtime_policy_blocks_dangerous_pod_settings(self):
        policy = RUNTIME_POLICY.read_text(encoding="utf-8")

        for rule in [
            "disallow-privileged-containers",
            "disallow-hostpath",
            "disallow-host-namespaces",
            "disallow-privilege-escalation",
            "require-resource-limits",
            "require-runasnonroot",
            "require-seccomp-runtime-default",
        ]:
            with self.subTest(rule=rule):
                self.assertIn(f"name: {rule}", policy)

    def test_runtime_manifest_uses_restricted_controls(self):
        manifest = RUNTIME_MANIFEST.read_text(encoding="utf-8")

        required = [
            "pod-security.kubernetes.io/enforce: restricted",
            "automountServiceAccountToken: false",
            "runAsNonRoot: true",
            "allowPrivilegeEscalation: false",
            "readOnlyRootFilesystem: true",
            "type: RuntimeDefault",
            "kind: NetworkPolicy",
            "kind: ResourceQuota",
            "kind: LimitRange",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, manifest)

        forbidden = ["hostPath:", "hostNetwork: true", "hostPID: true", "privileged: true"]
        for item in forbidden:
            with self.subTest(item=item):
                self.assertNotIn(item, manifest)

    def test_platform_services_chart_has_security_workload_controls(self):
        deployment = (PLATFORM_CHART / "templates" / "deployments.yaml").read_text(encoding="utf-8")
        values = (PLATFORM_CHART / "values.yaml").read_text(encoding="utf-8")

        for item in [
            "runAsNonRoot: true",
            "allowPrivilegeEscalation: false",
            "readOnlyRootFilesystem:",
            "seccompProfile:",
            "type: RuntimeDefault",
            "readinessProbe:",
            "livenessProbe:",
            "resources:",
        ]:
            with self.subTest(item=item):
                self.assertIn(item, deployment)

        for service in ["api", "dashboard", "billing-service", "provisioner-service", "deployment-worker", "notification-service", "metering-service"]:
            with self.subTest(service=service):
                self.assertIn(f"  {service}:", values)
