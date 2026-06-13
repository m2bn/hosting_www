from dataclasses import dataclass, field

from django.utils import timezone

from apps.api import audit_log
from apps.api.models import ArtifactScan, ArtifactScanStatus, ArtifactScanType


class ScanPolicyViolation(Exception):
    def __init__(self, message, code="artifact_scan_blocked", scan=None):
        super().__init__(message)
        self.code = code
        self.scan = scan


class ScanOverrideError(Exception):
    def __init__(self, message, code="scan_override_denied"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArtifactScanResult:
    scanner: str
    report_ref: str = ""
    sbom_ref: str = ""
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    infected: bool = False
    findings: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class StaticZipScanner:
    scanner_name = "static-zip-policy"

    def scan(self, artifact):
        findings = []
        for item in artifact.manifest:
            path = str(item.get("path", "")).lower()
            digest = str(item.get("sha256", "")).lower()
            if "malware" in path or "eicar" in path or digest.startswith("eicar"):
                findings.append(
                    {
                        "severity": "critical",
                        "category": "malware",
                        "title": "Blocked file pattern detected",
                    }
                )
        return ArtifactScanResult(
            scanner=self.scanner_name,
            critical_count=len(findings),
            infected=bool(findings),
            findings=findings,
            summary={"files": len(artifact.manifest), "bytes": artifact.total_size},
        )


class DependencyScanner:
    scanner_name = "dependency-policy"

    def scan(self, *, manifest_name, dependencies):
        findings = []
        for dependency in dependencies:
            if "critical" in str(dependency).lower():
                findings.append(
                    {
                        "severity": "critical",
                        "category": "dependency",
                        "title": "Critical dependency vulnerability",
                    }
                )
        return ArtifactScanResult(
            scanner=self.scanner_name,
            critical_count=len(findings),
            findings=findings,
            summary={"manifest": manifest_name, "dependency_count": len(dependencies)},
        )


def result_from_container_scan(scan_result):
    return ArtifactScanResult(
        scanner="container-image-policy",
        report_ref=scan_result.report_ref,
        sbom_ref=scan_result.sbom_ref,
        critical_count=scan_result.critical_count,
        high_count=scan_result.high_count,
        findings=[],
        summary={
            "critical": scan_result.critical_count,
            "high": scan_result.high_count,
        },
    )


def create_scan_record(
    *,
    organization,
    project,
    environment=None,
    build_job=None,
    deployment=None,
    scan_type,
    artifact_ref,
    result,
    request=None,
    actor=None,
):
    blocked = result.infected or result.critical_count > 0
    status = ArtifactScanStatus.BLOCKED if blocked else ArtifactScanStatus.CLEAN
    blocked_reason = ""
    if result.infected:
        blocked_reason = "Artifact scanner detected malware indicators."
    elif result.critical_count > 0:
        blocked_reason = "Artifact scanner detected critical vulnerabilities."

    scan = ArtifactScan.objects.create(
        organization=organization,
        project=project,
        environment=environment,
        build_job=build_job,
        deployment=deployment,
        scan_type=scan_type,
        artifact_ref=str(artifact_ref),
        status=status,
        scanner=result.scanner,
        report_ref=result.report_ref,
        sbom_ref=result.sbom_ref,
        summary=result.summary,
        findings=_public_findings(result.findings),
        critical_count=result.critical_count,
        high_count=result.high_count,
        medium_count=result.medium_count,
        low_count=result.low_count,
        blocked_reason=blocked_reason,
    )
    audit_log.record(
        action=audit_log.AuditAction.ARTIFACT_SCAN_BLOCKED if blocked else audit_log.AuditAction.ARTIFACT_SCAN_COMPLETED,
        request=request,
        actor=actor,
        organization=organization,
        project=project,
        target_type="artifact_scan",
        target_id=scan.public_id,
        metadata={
            "scan_type": scan.scan_type,
            "status": scan.status,
            "critical_count": scan.critical_count,
            "high_count": scan.high_count,
        },
    )
    return scan


def scan_static_artifact(*, organization, project, environment, build_job, deployment, artifact, request=None, actor=None, scanner=None):
    scanner = scanner or StaticZipScanner()
    result = scanner.scan(artifact)
    return create_scan_record(
        organization=organization,
        project=project,
        environment=environment,
        build_job=build_job,
        deployment=deployment,
        scan_type=ArtifactScanType.STATIC_ZIP,
        artifact_ref=build_job.source_ref,
        result=result,
        request=request,
        actor=actor,
    )


def record_container_scan(*, organization, project, environment, build_job, deployment, image_ref, scan_result, request=None, actor=None):
    result = result_from_container_scan(scan_result)
    return create_scan_record(
        organization=organization,
        project=project,
        environment=environment,
        build_job=build_job,
        deployment=deployment,
        scan_type=ArtifactScanType.CONTAINER_IMAGE,
        artifact_ref=image_ref,
        result=result,
        request=request,
        actor=actor,
    )


def enforce_scan_policy(scan):
    if scan.status == ArtifactScanStatus.OVERRIDDEN:
        return
    if scan.status == ArtifactScanStatus.BLOCKED:
        code = "infected_artifact" if scan.blocked_reason.lower().find("malware") >= 0 else "critical_vulnerability"
        raise ScanPolicyViolation("Deployment blocked by artifact scanning policy.", code=code, scan=scan)


def override_scan(scan, *, operator, reason, request=None):
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ScanOverrideError("Override reason is required.", code="reason_required")
    if not operator or not operator.is_authenticated or not operator.is_platform_staff:
        raise ScanOverrideError("Operator access required.", code="operator_required")
    if not operator.mfa_enabled:
        raise ScanOverrideError("Two-factor verification required for scan override.", code="operator_2fa_required")
    if scan.status != ArtifactScanStatus.BLOCKED:
        raise ScanOverrideError("Only blocked scan results can be overridden.", code="scan_not_blocked")

    scan.status = ArtifactScanStatus.OVERRIDDEN
    scan.overridden_by_user = operator
    scan.override_reason = clean_reason
    scan.overridden_at = timezone.now()
    scan.save(update_fields=["status", "overridden_by_user", "override_reason", "overridden_at", "updated_at"])
    audit_log.record(
        action=audit_log.AuditAction.ARTIFACT_SCAN_OVERRIDE,
        request=request,
        actor=operator,
        organization=scan.organization,
        project=scan.project,
        target_type="artifact_scan",
        target_id=scan.public_id,
        metadata={"reason": clean_reason, "scan_type": scan.scan_type},
    )
    return scan


def serialize_scan(scan, *, include_operator_details=False):
    data = {
        "public_id": str(scan.public_id),
        "organization_id": str(scan.organization.public_id),
        "project_id": str(scan.project.public_id),
        "deployment_id": str(scan.deployment.public_id) if scan.deployment else None,
        "build_job_id": str(scan.build_job.public_id) if scan.build_job else None,
        "scan_type": scan.scan_type,
        "status": scan.status,
        "scanner": scan.scanner,
        "critical_count": scan.critical_count,
        "high_count": scan.high_count,
        "medium_count": scan.medium_count,
        "low_count": scan.low_count,
        "summary": scan.summary,
        "findings": scan.findings,
        "created_at": scan.created_at.isoformat(),
        "overridden_at": scan.overridden_at.isoformat() if scan.overridden_at else None,
    }
    if include_operator_details:
        data["blocked_reason"] = scan.blocked_reason
        data["override_reason"] = scan.override_reason
        data["overridden_by"] = scan.overridden_by_user.email if scan.overridden_by_user else None
        data["report_ref"] = scan.report_ref
        data["sbom_ref"] = scan.sbom_ref
    return data


def _public_findings(findings):
    public = []
    for finding in findings:
        public.append(
            {
                "severity": finding.get("severity", "unknown"),
                "category": finding.get("category", "unknown"),
                "title": finding.get("title", "Security finding"),
            }
        )
    return public
