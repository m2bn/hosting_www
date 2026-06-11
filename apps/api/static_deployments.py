import hashlib
import json
import mimetypes
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.api import audit_log
from apps.api.entitlements import can_deploy_static_site, get_storage_limit
from apps.api.models import BuildJob, BuildJobStatus, Deployment, DeploymentStatus, SourceType, UsageMetric, UsageRecord


class StaticDeploymentError(Exception):
    def __init__(self, message, code="static_deployment_error"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StaticArtifact:
    manifest: list
    total_size: int
    root: Path


def deploy_static_zip(*, organization, project, environment, uploaded_file, actor, request=None):
    entitlement = can_deploy_static_site(project)
    if not entitlement.allowed:
        raise StaticDeploymentError("Deployment is not allowed by current entitlements.", code="entitlement_denied")
    _validate_upload(uploaded_file)

    build_job = None
    deployment = None
    try:
        with tempfile.TemporaryDirectory(prefix="static-deploy-") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "upload.zip"
            with archive_path.open("wb") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            artifact = unpack_static_zip(archive_path, temp_path / "site")
            _check_storage_limit(organization, artifact.total_size)
            prefix = _deployment_prefix(organization, project, None)
            with transaction.atomic():
                build_job = BuildJob.objects.create(
                    organization=organization,
                    project=project,
                    environment=environment,
                    requested_by_user=actor,
                    source_type=SourceType.UPLOAD,
                    source_ref=f"static-upload:{uploaded_file.name}",
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
                    status=DeploymentStatus.DEPLOYING,
                    requested_by_user=actor,
                    started_at=timezone.now(),
                )
                prefix = _deployment_prefix(organization, project, deployment)
                storage = StaticDeploymentStorage()
                upload_result = storage.upload_directory(artifact.root, prefix, artifact.manifest)
                logs_ref = storage.write_text(
                    f"{prefix}/deployment.log",
                    "\n".join(
                        [
                            "static deployment accepted",
                            f"files={len(artifact.manifest)}",
                            f"bytes={artifact.total_size}",
                        ]
                    ),
                )
                build_job.status = BuildJobStatus.SUCCEEDED
                build_job.logs_ref = logs_ref
                build_job.finished_at = timezone.now()
                build_job.save(update_fields=["status", "logs_ref", "finished_at", "updated_at"])
                Deployment.objects.filter(
                    organization=organization,
                    project=project,
                    environment=environment,
                    status=DeploymentStatus.RUNNING,
                ).exclude(pk=deployment.pk).update(status=DeploymentStatus.ROLLED_BACK, finished_at=timezone.now())
                deployment.image_ref = upload_result["artifact_ref"]
                deployment.status = DeploymentStatus.RUNNING
                deployment.finished_at = timezone.now()
                deployment.save(update_fields=["image_ref", "status", "finished_at", "updated_at"])
                _record_storage_usage(organization, project, environment, artifact.total_size)
                audit_log.record(
                    action=audit_log.AuditAction.DEPLOYMENT_STARTED,
                    request=request,
                    actor=actor,
                    organization=organization,
                    project=project,
                    target_type="deployment",
                    target_id=deployment.public_id,
                    metadata={"type": "static_site", "file_count": len(artifact.manifest), "bytes": artifact.total_size},
                )
                audit_log.record(
                    action=audit_log.AuditAction.DEPLOYMENT_ACTIVATED,
                    request=request,
                    actor=actor,
                    organization=organization,
                    project=project,
                    target_type="deployment",
                    target_id=deployment.public_id,
                    metadata={"artifact_ref": deployment.image_ref},
                )
    except StaticDeploymentError:
        if build_job:
            build_job.status = BuildJobStatus.FAILED
            build_job.finished_at = timezone.now()
            build_job.save(update_fields=["status", "finished_at", "updated_at"])
        if deployment:
            deployment.status = DeploymentStatus.FAILED
            deployment.finished_at = timezone.now()
            deployment.save(update_fields=["status", "finished_at", "updated_at"])
        raise
    return deployment


def unpack_static_zip(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    total_size = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) > settings.STATIC_DEPLOYMENT_MAX_FILES:
                raise StaticDeploymentError("Too many files in ZIP.", code="too_many_files")
            for info in infos:
                path = _safe_member_path(destination, info.filename)
                _validate_member(info)
                total_size += info.file_size
                if total_size > settings.STATIC_DEPLOYMENT_MAX_UNPACKED_BYTES:
                    raise StaticDeploymentError("Unpacked content is too large.", code="unpacked_too_large")
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                digest = _sha256(path)
                manifest.append(
                    {
                        "path": path.relative_to(destination).as_posix(),
                        "size": info.file_size,
                        "sha256": digest,
                        "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    }
                )
    except zipfile.BadZipFile as exc:
        raise StaticDeploymentError("Invalid ZIP archive.", code="invalid_zip") from exc
    if not manifest:
        raise StaticDeploymentError("ZIP does not contain deployable files.", code="empty_archive")
    return StaticArtifact(manifest=manifest, total_size=total_size, root=destination)


def rollback_static_deployment(*, organization, project, environment, deployment_public_id, actor, request=None):
    with transaction.atomic():
        target = Deployment.objects.select_for_update().get(
            organization=organization,
            project=project,
            environment=environment,
            public_id=deployment_public_id,
        )
        if not target.image_ref:
            raise StaticDeploymentError("Deployment cannot be rolled back.", code="rollback_not_available")
        Deployment.objects.filter(
            organization=organization,
            project=project,
            environment=environment,
            status=DeploymentStatus.RUNNING,
        ).exclude(pk=target.pk).update(status=DeploymentStatus.ROLLED_BACK, finished_at=timezone.now())
        target.status = DeploymentStatus.RUNNING
        target.finished_at = timezone.now()
        target.save(update_fields=["status", "finished_at", "updated_at"])
        audit_log.record(
            action=audit_log.AuditAction.DEPLOYMENT_ROLLED_BACK,
            request=request,
            actor=actor,
            organization=organization,
            project=project,
            target_type="deployment",
            target_id=target.public_id,
            metadata={"artifact_ref": target.image_ref},
        )
    return target


class StaticDeploymentStorage:
    def upload_directory(self, root, prefix, manifest):
        if settings.STATIC_DEPLOYMENT_STORAGE_BACKEND == "s3":
            return self._upload_s3(root, prefix, manifest)
        return self._upload_local(root, prefix, manifest)

    def write_text(self, key, content):
        if settings.STATIC_DEPLOYMENT_STORAGE_BACKEND == "s3":
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.STATIC_DEPLOYMENT_S3_ENDPOINT_URL or None,
                region_name=settings.STATIC_DEPLOYMENT_S3_REGION,
            )
            client.put_object(Bucket=settings.STATIC_DEPLOYMENT_S3_BUCKET, Key=key, Body=content.encode("utf-8"))
            return f"s3://{settings.STATIC_DEPLOYMENT_S3_BUCKET}/{key}"
        path = Path(settings.STATIC_DEPLOYMENT_LOCAL_ROOT) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _upload_local(self, root, prefix, manifest):
        destination = Path(settings.STATIC_DEPLOYMENT_LOCAL_ROOT) / prefix
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for item in manifest:
            source = root / item["path"]
            target = destination / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"artifact_ref": str(destination), "manifest_ref": str(destination / "manifest.json")}

    def _upload_s3(self, root, prefix, manifest):
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.STATIC_DEPLOYMENT_S3_ENDPOINT_URL or None,
            region_name=settings.STATIC_DEPLOYMENT_S3_REGION,
        )
        for item in manifest:
            key = f"{prefix}/{item['path']}"
            client.upload_file(str(root / item["path"]), settings.STATIC_DEPLOYMENT_S3_BUCKET, key, ExtraArgs={"ContentType": item["content_type"]})
        manifest_key = f"{prefix}/manifest.json"
        client.put_object(Bucket=settings.STATIC_DEPLOYMENT_S3_BUCKET, Key=manifest_key, Body=json.dumps(manifest).encode("utf-8"))
        return {"artifact_ref": f"s3://{settings.STATIC_DEPLOYMENT_S3_BUCKET}/{prefix}", "manifest_ref": f"s3://{settings.STATIC_DEPLOYMENT_S3_BUCKET}/{manifest_key}"}


def _validate_upload(uploaded_file):
    if not uploaded_file.name.lower().endswith(".zip"):
        raise StaticDeploymentError("Only ZIP uploads are supported.", code="invalid_extension")
    if uploaded_file.content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
        raise StaticDeploymentError("Invalid ZIP MIME type.", code="invalid_mime")
    if uploaded_file.size > settings.STATIC_DEPLOYMENT_MAX_ZIP_BYTES:
        raise StaticDeploymentError("ZIP is too large.", code="zip_too_large")


def _validate_member(info):
    mode = info.external_attr >> 16
    if mode & 0o170000 == 0o120000:
        raise StaticDeploymentError("Symlinks are not allowed.", code="symlink_not_allowed")
    extension = PurePosixPath(info.filename).suffix.lower()
    if extension not in settings.STATIC_DEPLOYMENT_ALLOWED_EXTENSIONS:
        raise StaticDeploymentError("File type is not allowed.", code="file_type_not_allowed")


def _safe_member_path(destination, filename):
    member_path = PurePosixPath(filename)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise StaticDeploymentError("Invalid ZIP path.", code="zip_slip")
    resolved = (destination / Path(*member_path.parts)).resolve()
    if not str(resolved).startswith(str(destination.resolve())):
        raise StaticDeploymentError("Invalid ZIP path.", code="zip_slip")
    return resolved


def _check_storage_limit(organization, new_bytes):
    limit_gb = get_storage_limit(organization)
    if limit_gb is None:
        return
    current = UsageRecord.objects.filter(organization=organization, metric=UsageMetric.STORAGE_GB_HOURS).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
    new_gb = Decimal(new_bytes) / Decimal(1024**3)
    if current + new_gb > Decimal(limit_gb):
        raise StaticDeploymentError("Storage limit exceeded.", code="storage_limit_exceeded")


def _record_storage_usage(organization, project, environment, total_bytes):
    now = timezone.now()
    UsageRecord.objects.create(
        organization=organization,
        project=project,
        environment=environment,
        metric=UsageMetric.STORAGE_GB_HOURS,
        quantity=Decimal(total_bytes) / Decimal(1024**3),
        unit="gb",
        period_start=now,
        period_end=now + timedelta(seconds=1),
        source="static_deployment",
    )


def _deployment_prefix(organization, project, deployment):
    deployment_id = str(deployment.public_id) if deployment else "pending"
    return f"{organization.public_id}/{project.public_id}/{deployment_id}"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
