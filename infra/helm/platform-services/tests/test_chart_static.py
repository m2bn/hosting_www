import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = [
    "api",
    "dashboard",
    "billing-service",
    "provisioner-service",
    "deployment-worker",
    "notification-service",
    "metering-service",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_all_platform_services_are_declared() -> None:
    values = read("values.yaml")

    for service in SERVICES:
        assert f"  {service}:" in values
        assert "resources:" in values
        assert "secretKeys:" in values


def test_required_templates_exist() -> None:
    expected_templates = [
        "templates/configmaps.yaml",
        "templates/deployments.yaml",
        "templates/hpas.yaml",
        "templates/networkpolicies.yaml",
        "templates/pdbs.yaml",
        "templates/secrets.yaml",
        "templates/serviceaccount.yaml",
        "templates/services.yaml",
    ]

    for template in expected_templates:
        assert (ROOT / template).exists(), template


def test_deployment_template_contains_security_baseline() -> None:
    deployment = read("templates/deployments.yaml")

    required_fragments = [
        "runAsNonRoot: true",
        "allowPrivilegeEscalation: false",
        "readOnlyRootFilesystem:",
        "seccompProfile:",
        "type: RuntimeDefault",
        "readinessProbe:",
        "livenessProbe:",
        "resources:",
        "envFrom:",
        "configMapRef:",
        "secretRef:",
    ]

    for fragment in required_fragments:
        assert fragment in deployment


def test_network_policy_and_availability_controls_are_present() -> None:
    network_policy = read("templates/networkpolicies.yaml")
    pdb = read("templates/pdbs.yaml")
    hpa = read("templates/hpas.yaml")

    assert "kind: NetworkPolicy" in network_policy
    assert "policyTypes:" in network_policy
    assert "- Ingress" in network_policy
    assert "- Egress" in network_policy
    assert "kind: PodDisruptionBudget" in pdb
    assert "kind: HorizontalPodAutoscaler" in hpa


def test_values_do_not_contain_secret_values() -> None:
    suspicious_patterns = [
        re.compile(r"^\s*(password|secret|token|api_key|private_key)\s*:", re.IGNORECASE),
        re.compile(r"BEGIN [A-Z ]+PRIVATE KEY", re.IGNORECASE),
    ]
    values_files = ["values.yaml", "values-staging.yaml", "values-production.yaml"]

    for values_file in values_files:
        for line in read(values_file).splitlines():
            for pattern in suspicious_patterns:
                assert not pattern.search(line), f"{values_file} contains suspicious line: {line}"


if __name__ == "__main__":
    test_all_platform_services_are_declared()
    test_required_templates_exist()
    test_deployment_template_contains_security_baseline()
    test_network_policy_and_availability_controls_are_present()
    test_values_do_not_contain_secret_values()
    print("platform-services chart static tests passed")
