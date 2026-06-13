import fnmatch
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.api import artifact_scanning, audit_log
from apps.api.entitlements import can_deploy_project
from apps.api.models import BuildJob, BuildJobStatus, Deployment, DeploymentStatus, RuntimeInstance, RuntimeInstanceStatus, SourceType


class ContainerDeploymentError(Exception):
    def __init__(self, message, code="container_deployment_error"):
        super().__init__(message)
        self.code = code


class ContainerBuildTimeout(ContainerDeploymentError):
    def __init__(self, message="Container build timed out."):
        super().__init__(message, code="build_timeout")


@dataclass(frozen=True)
class BuildContextArtifact:
    root: Path
    total_size: int
    files: list


@dataclass(frozen=True)
class BuildResult:
    image_ref: str
    image_digest: str
    logs_ref: str


@dataclass(frozen=True)
class ScanResult:
    report_ref: str
    sbom_ref: str
    critical_count: int = 0
    high_count: int = 0


class DockerignoreMatcher:
    def __init__(self, patterns):
        self.patterns = [pattern.strip() for pattern in patterns if pattern.strip() and not pattern.strip().startswith("#")]

    @classmethod
    def from_root(cls, root):
        path = root / ".dockerignore"
        if not path.exists():
            return cls([])
        return cls(path.read_text(encoding="utf-8").splitlines())

    def matches(self, relative_path):
        normalized = relative_path.as_posix()
        for pattern in self.patterns:
            clean = pattern.lstrip("/")
            if clean.endswith("/") and (normalized == clean[:-1] or normalized.startswith(clean)):
                return True
            if fnmatch.fnmatch(normalized, clean) or fnmatch.fnmatch(relative_path.name, clean):
                return True
        return False


class ContainerRegistryClient:
    def build_and_push(self, *, context_root, image_ref, build_spec):
        if build_spec["timeout_seconds"] <= 0:
            raise ContainerBuildTimeout()
        return BuildResult(
            image_ref=image_ref,
            image_digest=f"sha256:{Path(image_ref).name.replace(':', '-')}",
            logs_ref=f"container-build-logs://{build_spec['build_job_public_id']}",
        )


class ImageScanner:
    def scan(self, *, image_ref, image_digest):
        return ScanResult(
            report_ref=f"image-scan://{image_digest}",
            sbom_ref=f"sbom://{image_digest}",
            critical_count=0,
            high_count=0,
        )


class KubernetesRuntimeClient:
    def deploy(self, deployment_spec):
        return {
            "namespace": deployment_spec["namespace"],
            "workload_name": deployment_spec["workload_name"],
            "ready": True,
        }

    def rollback(self, rollback_spec):
        return {
            "namespace": rollback_spec["namespace"],
            "workload_name": rollback_spec["workload_name"],
            "rolled_back_to": rollback_spec["target_image_ref"],
        }


def deploy_container_from_zip(
    *,
    organization,
    project,
    environment,
    uploaded_file,
    actor,
    request=None,
    registry_client=None,
    scanner=None,
    runtime_client=None,
):
    entitlement = can_deploy_project(project)
    if not entitlement.allowed:
        raise ContainerDeploymentError("Deployment is not allowed by current entitlements.", code="entitlement_denied")
    _validate_upload(uploaded_file)
    registry_client = registry_client or ContainerRegistryClient()
    scanner = scanner or ImageScanner()
    runtime_client = runtime_client or KubernetesRuntimeClient()

    build_job = None
    deployment = None
    try:
        with tempfile.TemporaryDirectory(prefix="container-build-") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "context.zip"
            with archive_path.open("wb") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            context = unpack_build_context(archive_path, temp_path / "context")

            with transaction.atomic():
                build_job = BuildJob.objects.create(
                    organization=organization,
                    project=project,
                    environment=environment,
                    requested_by_user=actor,
                    source_type=SourceType.UPLOAD,
                    source_ref=f"container-upload:{uploaded_file.name}",
                    status=BuildJobStatus.RUNNING,
                    started_at=timezone.now(),
                )
                deployment = Deployment.objects.create(
                    organization=organization,
                    project=project,
                    environment=environment,
                    build_job=build_job,
                    version=str(build_job.public_id),
                    image_ref="pending",
                    status=DeploymentStatus.BUILDING,
                    requested_by_user=actor,
                    started_at=timezone.now(),
                )

            image_ref = _image_ref(organization, project, deployment)
            build_spec = _build_spec(organization, project, environment, build_job, context)
            build_result = registry_client.build_and_push(context_root=context.root, image_ref=image_ref, build_spec=build_spec)
            scan_result = scanner.scan(image_ref=build_result.image_ref, image_digest=build_result.image_digest)
            scan = artifact_scanning.record_container_scan(
                organization=organization,
                project=project,
                environment=environment,
                build_job=build_job,
                deployment=deployment,
                image_ref=build_result.image_ref,
                scan_result=scan_result,
                request=request,
                actor=actor,
            )
            try:
                artifact_scanning.enforce_scan_policy(scan)
            except artifact_scanning.ScanPolicyViolation as exc:
                raise ContainerDeploymentError(str(exc), code=exc.code) from exc
            deploy_spec = _runtime_deployment_spec(environment, deployment, build_result)
            runtime_result = runtime_client.deploy(deploy_spec)

            with transaction.atomic():
                build_job.image_ref = build_result.image_ref
                build_job.sbom_ref = scan_result.sbom_ref
                build_job.logs_ref = build_result.logs_ref
                build_job.status = BuildJobStatus.SUCCEEDED
                build_job.finished_at = timezone.now()
                build_job.save(update_fields=["image_ref", "sbom_ref", "logs_ref", "status", "finished_at", "updated_at"])
                Deployment.objects.filter(
                    organization=organization,
                    project=project,
                    environment=environment,
                    status=DeploymentStatus.RUNNING,
                ).exclude(pk=deployment.pk).update(status=DeploymentStatus.ROLLED_BACK, finished_at=timezone.now())
                RuntimeInstance.objects.filter(
                    organization=organization,
                    project=project,
                    environment=environment,
                    status__in=[RuntimeInstanceStatus.PENDING, RuntimeInstanceStatus.RUNNING, RuntimeInstanceStatus.DEGRADED],
                ).update(status=RuntimeInstanceStatus.TERMINATED, last_observed_at=timezone.now())
                deployment.image_ref = build_result.image_ref
                deployment.status = DeploymentStatus.RUNNING
                deployment.finished_at = timezone.now()
                deployment.save(update_fields=["image_ref", "status", "finished_at", "updated_at"])
                RuntimeInstance.objects.create(
                    organization=organization,
                    project=project,
                    environment=environment,
                    deployment=deployment,
                    kubernetes_namespace=environment.kubernetes_namespace,
                    workload_name=runtime_result["workload_name"],
                    status=RuntimeInstanceStatus.RUNNING,
                    replica_count=1,
                    last_observed_at=timezone.now(),
                )
                audit_log.record(
                    action=audit_log.AuditAction.DEPLOYMENT_STARTED,
                    request=request,
                    actor=actor,
                    organization=organization,
                    project=project,
                    target_type="deployment",
                    target_id=deployment.public_id,
                    metadata={"type": "container", "context_bytes": context.total_size, "files": len(context.files)},
                )
                audit_log.record(
                    action=audit_log.AuditAction.DEPLOYMENT_ACTIVATED,
                    request=request,
                    actor=actor,
                    organization=organization,
                    project=project,
                    target_type="deployment",
                    target_id=deployment.public_id,
                    metadata={"image_ref": deployment.image_ref, "image_digest": build_result.image_digest, "scan_report_ref": scan_result.report_ref},
                )
    except ContainerDeploymentError as exc:
        _mark_failed(build_job, deployment)
        audit_log.record(
            action=audit_log.AuditAction.DEPLOYMENT_FAILED,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="deployment",
            target_id=deployment.public_id if deployment else "",
            metadata={"code": exc.code},
        )
        raise
    return deployment


def rollback_container_deployment(*, organization, project, environment, deployment_public_id, actor, request=None, runtime_client=None):
    runtime_client = runtime_client or KubernetesRuntimeClient()
    with transaction.atomic():
        target = Deployment.objects.select_for_update().get(
            organization=organization,
            project=project,
            environment=environment,
            public_id=deployment_public_id,
        )
        if not target.image_ref or target.image_ref == "pending":
            raise ContainerDeploymentError("Deployment cannot be rolled back.", code="rollback_not_available")
        runtime_client.rollback(
            {
                "namespace": environment.kubernetes_namespace,
                "workload_name": _workload_name(project, environment),
                "target_image_ref": target.image_ref,
            }
        )
        Deployment.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            status=DeploymentStatus.RUNNING,
        ).exclude(pk=target.pk).update(status=DeploymentStatus.ROLLED_BACK, finished_at=timezone.now())
        RuntimeInstance.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            status__in=[RuntimeInstanceStatus.PENDING, RuntimeInstanceStatus.RUNNING, RuntimeInstanceStatus.DEGRADED],
        ).update(status=RuntimeInstanceStatus.TERMINATED, last_observed_at=timezone.now())
        target.status = DeploymentStatus.RUNNING
        target.finished_at = timezone.now()
        target.save(update_fields=["status", "finished_at", "updated_at"])
        RuntimeInstance.objects.create(
            organization=organization,
            project=project,
            environment=environment,
            deployment=target,
            kubernetes_namespace=environment.kubernetes_namespace,
            workload_name=_workload_name(project, environment),
            status=RuntimeInstanceStatus.RUNNING,
            replica_count=1,
            last_observed_at=timezone.now(),
        )
        audit_log.record(
            action=audit_log.AuditAction.DEPLOYMENT_ROLLED_BACK,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="deployment",
            target_id=target.public_id,
            metadata={"image_ref": target.image_ref},
        )
    return target


def unpack_build_context(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                _validate_member(info)
                path = _safe_member_path(destination, info.filename)
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, path.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except zipfile.BadZipFile as exc:
        raise ContainerDeploymentError("Invalid ZIP archive.", code="invalid_zip") from exc

    dockerfile = destination / "Dockerfile"
    if not dockerfile.exists() or not dockerfile.is_file():
        raise ContainerDeploymentError("Dockerfile is required.", code="dockerfile_missing")

    matcher = DockerignoreMatcher.from_root(destination)
    files = []
    total_size = 0
    for path in destination.rglob("*"):
        relative = path.relative_to(destination)
        if matcher.matches(relative):
            continue
        if path.is_symlink():
            raise ContainerDeploymentError("Symlinks are not allowed in build context.", code="symlink_not_allowed")
        if path.is_file():
            size = path.stat().st_size
            total_size += size
            if total_size > settings.CONTAINER_DEPLOYMENT_MAX_CONTEXT_BYTES:
                raise ContainerDeploymentError("Build context is too large.", code="context_too_large")
            files.append({"path": relative.as_posix(), "size": size})
    return BuildContextArtifact(root=destination, total_size=total_size, files=files)


def _validate_upload(uploaded_file):
    if not uploaded_file.name.lower().endswith(".zip"):
        raise ContainerDeploymentError("Only ZIP build contexts are supported.", code="invalid_extension")
    if uploaded_file.content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
        raise ContainerDeploymentError("Invalid ZIP MIME type.", code="invalid_mime")
    if uploaded_file.size > settings.CONTAINER_DEPLOYMENT_MAX_CONTEXT_ZIP_BYTES:
        raise ContainerDeploymentError("Build context ZIP is too large.", code="zip_too_large")


def _validate_member(info):
    mode = info.external_attr >> 16
    if mode & 0o170000 == 0o120000:
        raise ContainerDeploymentError("Symlinks are not allowed in build context.", code="symlink_not_allowed")


def _safe_member_path(destination, filename):
    member_path = PurePosixPath(filename)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ContainerDeploymentError("Invalid build context path.", code="zip_slip")
    resolved = (destination / Path(*member_path.parts)).resolve()
    if not str(resolved).startswith(str(destination.resolve())):
        raise ContainerDeploymentError("Invalid build context path.", code="zip_slip")
    return resolved


def _image_ref(organization, project, deployment):
    registry = settings.CONTAINER_DEPLOYMENT_REGISTRY.rstrip("/")
    return f"{registry}/{organization.public_id}/{project.public_id}/{deployment.public_id}:latest"


def _build_spec(organization, project, environment, build_job, context):
    return {
        "organization_public_id": str(organization.public_id),
        "project_public_id": str(project.public_id),
        "environment_public_id": str(environment.public_id),
        "build_job_public_id": str(build_job.public_id),
        "isolated_namespace": f"build-{str(build_job.public_id)[:12]}",
        "timeout_seconds": settings.CONTAINER_DEPLOYMENT_BUILD_TIMEOUT_SECONDS,
        "context_bytes": context.total_size,
        "cpu_limit": settings.CONTAINER_DEPLOYMENT_BUILD_CPU_LIMIT,
        "memory_limit": settings.CONTAINER_DEPLOYMENT_BUILD_MEMORY_LIMIT,
        "privileged": False,
        "hostPath": False,
        "control_plane_secrets": [],
    }


def _runtime_deployment_spec(environment, deployment, build_result):
    port = settings.CONTAINER_DEPLOYMENT_DEFAULT_PORT
    return {
        "namespace": environment.kubernetes_namespace,
        "workload_name": _workload_name(deployment.project, environment),
        "image_ref": build_result.image_ref,
        "image_digest": build_result.image_digest,
        "readinessProbe": {"httpGet": {"path": "/", "port": port}},
        "livenessProbe": {"httpGet": {"path": "/", "port": port}},
        "resources": {
            "limits": {
                "cpu": settings.CONTAINER_DEPLOYMENT_RUNTIME_CPU_LIMIT,
                "memory": settings.CONTAINER_DEPLOYMENT_RUNTIME_MEMORY_LIMIT,
            }
        },
        "networkPolicyRequired": True,
        "securityContext": {
            "privileged": False,
            "allowPrivilegeEscalation": False,
            "runAsNonRoot": True,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
    }


def _workload_name(project, environment):
    return f"{project.slug}-{environment.slug}"[:253]


def _mark_failed(build_job, deployment):
    if build_job:
        build_job.status = BuildJobStatus.FAILED
        build_job.finished_at = timezone.now()
        build_job.save(update_fields=["status", "finished_at", "updated_at"])
    if deployment:
        deployment.status = DeploymentStatus.FAILED
        deployment.finished_at = timezone.now()
        deployment.save(update_fields=["status", "finished_at", "updated_at"])


def deployment_logs(deployment):
    if not deployment.build_job or not deployment.build_job.logs_ref:
        return []
    return [
        "container deployment accepted",
        f"image={deployment.image_ref}",
        f"logs_ref={deployment.build_job.logs_ref}",
        json.dumps({"status": deployment.status}),
    ]
