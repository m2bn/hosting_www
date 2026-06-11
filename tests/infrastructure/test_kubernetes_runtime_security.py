from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]
KUBERNETES_BASELINE = ROOT / "infra" / "kubernetes" / "customer-runtime-baseline.yaml"
HELM_DIR = ROOT / "infra" / "helm" / "customer-runtime"
POLICY_FILE = ROOT / "infra" / "policies" / "kyverno-runtime-baseline.yaml"


class KubernetesRuntimeSecurityTests(TestCase):
    def text(self, path):
        return path.read_text(encoding="utf-8")

    def test_baseline_manifest_has_namespace_isolation_and_pod_security(self):
        manifest = self.text(KUBERNETES_BASELINE)

        self.assertIn("kind: Namespace", manifest)
        self.assertIn("platform.example.com/project-id", manifest)
        self.assertIn("pod-security.kubernetes.io/enforce: restricted", manifest)
        self.assertIn("pod-security.kubernetes.io/audit: restricted", manifest)
        self.assertIn("pod-security.kubernetes.io/warn: restricted", manifest)

    def test_baseline_manifest_has_quota_limits_and_network_default_deny(self):
        manifest = self.text(KUBERNETES_BASELINE)

        self.assertIn("kind: ResourceQuota", manifest)
        self.assertIn("kind: LimitRange", manifest)
        self.assertIn("name: default-deny-ingress", manifest)
        self.assertIn("name: default-deny-egress", manifest)
        self.assertIn("name: allow-dns-egress", manifest)
        self.assertIn("policyTypes:\n    - Ingress", manifest)
        self.assertIn("policyTypes:\n    - Egress", manifest)

    def test_baseline_workload_uses_restricted_security_context(self):
        manifest = self.text(KUBERNETES_BASELINE)

        required = [
            "automountServiceAccountToken: false",
            "runAsNonRoot: true",
            "allowPrivilegeEscalation: false",
            "privileged: false",
            "readOnlyRootFilesystem: true",
            "type: RuntimeDefault",
            "drop:\n                - ALL",
            "limits:",
            "readinessProbe:",
            "livenessProbe:",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, manifest)

        forbidden = ["hostPath:", "hostNetwork: true", "hostPID: true", "privileged: true"]
        for item in forbidden:
            with self.subTest(item=item):
                self.assertNotIn(item, manifest)

    def test_helm_chart_contains_required_templates(self):
        expected = {
            "namespace.yaml",
            "serviceaccount.yaml",
            "quota.yaml",
            "networkpolicy.yaml",
            "deployment.yaml",
            "service.yaml",
        }
        actual = {path.name for path in (HELM_DIR / "templates").glob("*.yaml")}

        self.assertTrue(expected.issubset(actual))
        self.assertTrue((HELM_DIR / "Chart.yaml").exists())
        self.assertTrue((HELM_DIR / "values.yaml").exists())

    def test_helm_deployment_template_has_runtime_security_controls(self):
        deployment = self.text(HELM_DIR / "templates" / "deployment.yaml")

        required = [
            "automountServiceAccountToken: {{ .Values.runtime.automountServiceAccountToken }}",
            "runAsNonRoot: {{ .Values.runtime.runAsNonRoot }}",
            "seccompProfile:",
            "type: RuntimeDefault",
            "allowPrivilegeEscalation: false",
            "privileged: false",
            "readOnlyRootFilesystem: {{ .Values.runtime.readOnlyRootFilesystem }}",
            "readinessProbe:",
            "livenessProbe:",
            "resources:",
            "limits:",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, deployment)

    def test_kyverno_policy_blocks_required_dangerous_settings(self):
        policy = self.text(POLICY_FILE)

        required_rules = [
            "require-pod-security-restricted",
            "disallow-privileged-containers",
            "disallow-hostpath",
            "disallow-host-namespaces",
            "disallow-privilege-escalation",
            "require-resource-limits",
            "require-runasnonroot",
            "require-seccomp-runtime-default",
        ]
        for rule in required_rules:
            with self.subTest(rule=rule):
                self.assertIn(f"name: {rule}", policy)

        required_terms = [
            "privileged",
            "hostPath",
            "hostNetwork",
            "hostPID",
            "allowPrivilegeEscalation",
            "limits:",
            "runAsNonRoot",
            "seccompProfile",
            "RuntimeDefault",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, policy)
