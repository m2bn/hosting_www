import base64
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.utils import timezone


logger = logging.getLogger(__name__)


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    encrypted_path: Path
    sha256: str
    manifest: dict


@dataclass(frozen=True)
class RestoreCheckResult:
    backup_id: str
    ok: bool
    checks: list[dict] = field(default_factory=list)


def create_backup(*, output_dir=None, encryption_key=None, retention_days=None, now=None):
    now = now or timezone.now()
    backup_id = now.strftime("%Y%m%dT%H%M%SZ")
    output = Path(output_dir or settings.BACKUP_OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    key = _require_encryption_key(encryption_key)
    retention_days = settings.BACKUP_RETENTION_DAYS if retention_days is None else retention_days

    with tempfile.TemporaryDirectory(prefix="platform-backup-") as temp_dir:
        root = Path(temp_dir)
        payload_dir = root / "payload"
        payload_dir.mkdir()
        manifest = {
            "backup_id": backup_id,
            "created_at": now.isoformat(),
            "format_version": 1,
            "components": {},
        }
        _backup_postgresql(payload_dir, manifest)
        _backup_s3_metadata(payload_dir, manifest)
        _backup_deployment_files(payload_dir, manifest)
        _backup_platform_config(payload_dir, manifest)
        _backup_secret_fingerprints(payload_dir, manifest)
        manifest_path = payload_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        archive_path = root / f"{backup_id}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(payload_dir, arcname="payload")

        encrypted_path = output / f"{backup_id}.tar.gz.enc"
        encrypted = _fernet(key).encrypt(archive_path.read_bytes())
        encrypted_path.write_bytes(encrypted)
        digest = _sha256_bytes(encrypted)
        (output / f"{backup_id}.sha256").write_text(f"{digest}  {encrypted_path.name}\n", encoding="utf-8")
        _apply_retention(output, retention_days)
        logger.info("backup_created", extra={"backup_id": backup_id, "path": str(encrypted_path), "sha256": digest})
        return BackupResult(backup_id=backup_id, encrypted_path=encrypted_path, sha256=digest, manifest=manifest)


def verify_backup(*, encrypted_path, encryption_key=None):
    encrypted = Path(encrypted_path)
    key = _require_encryption_key(encryption_key)
    try:
        archive_bytes = _fernet(key).decrypt(encrypted.read_bytes())
    except (InvalidToken, OSError) as exc:
        raise BackupError("Backup cannot be decrypted or read.") from exc
    with tempfile.TemporaryDirectory(prefix="platform-backup-verify-") as temp_dir:
        archive_path = Path(temp_dir) / "backup.tar.gz"
        archive_path.write_bytes(archive_bytes)
        _safe_extract_tar(archive_path, Path(temp_dir) / "restore")
        manifest_path = Path(temp_dir) / "restore" / "payload" / "manifest.json"
        if not manifest_path.exists():
            raise BackupError("Backup manifest is missing.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = ["postgresql", "s3_metadata", "deployment_files", "platform_config", "secret_fingerprints"]
        checks = [{"name": name, "ok": name in manifest.get("components", {})} for name in required]
        return RestoreCheckResult(backup_id=manifest.get("backup_id", "unknown"), ok=all(item["ok"] for item in checks), checks=checks)


def restore_to_staging(*, encrypted_path, restore_dir, encryption_key=None, confirm_staging=False, target_environment=None):
    target_environment = target_environment or os.environ.get("APP_ENV", "development")
    if target_environment == "production":
        raise BackupError("Refusing to restore into production.")
    if target_environment != "staging" and not confirm_staging:
        raise BackupError("Restore requires staging target or explicit confirmation.")
    check = verify_backup(encrypted_path=encrypted_path, encryption_key=encryption_key)
    if not check.ok:
        raise BackupError("Backup failed verification checks.")
    destination = Path(restore_dir)
    destination.mkdir(parents=True, exist_ok=True)
    archive_bytes = _fernet(_require_encryption_key(encryption_key)).decrypt(Path(encrypted_path).read_bytes())
    with tempfile.TemporaryDirectory(prefix="platform-backup-restore-") as temp_dir:
        archive_path = Path(temp_dir) / "backup.tar.gz"
        archive_path.write_bytes(archive_bytes)
        _safe_extract_tar(archive_path, destination)
    logger.info("backup_restored_to_staging", extra={"backup_id": check.backup_id, "restore_dir": str(destination)})
    return check


def _backup_postgresql(payload_dir, manifest):
    target = payload_dir / "postgresql"
    target.mkdir()
    dump_path = target / "dump.sql"
    pg_dump = shutil.which("pg_dump")
    database = connections["default"].settings_dict
    if pg_dump and database.get("ENGINE") == "django.db.backends.postgresql":
        with dump_path.open("wb") as handle:
            subprocess.run(_pg_dump_command(pg_dump, database), check=True, stdout=handle, env=_pg_dump_environment(database))
        mode = "pg_dump"
    else:
        with dump_path.open("w", encoding="utf-8") as handle:
            call_command("dumpdata", "--natural-foreign", "--natural-primary", stdout=handle)
        mode = "django_dumpdata"
    manifest["components"]["postgresql"] = {"path": "postgresql/dump.sql", "mode": mode, "sha256": _sha256_file(dump_path)}


def _pg_dump_command(pg_dump, database):
    command = [pg_dump, "--no-owner", "--no-privileges"]
    name = database.get("NAME")
    if name:
        command.extend(["--dbname", str(name)])
    return command


def _pg_dump_environment(database):
    environment = os.environ.copy()
    mapping = {
        "HOST": "PGHOST",
        "PORT": "PGPORT",
        "USER": "PGUSER",
        "PASSWORD": "PGPASSWORD",
    }
    for setting_key, env_key in mapping.items():
        value = database.get(setting_key)
        if value:
            environment[env_key] = str(value)
    return environment


def _backup_s3_metadata(payload_dir, manifest):
    target = payload_dir / "s3"
    target.mkdir()
    metadata_path = target / "objects.json"
    objects = []
    if settings.STATIC_DEPLOYMENT_STORAGE_BACKEND == "s3" and settings.STATIC_DEPLOYMENT_S3_BUCKET:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.STATIC_DEPLOYMENT_S3_ENDPOINT_URL or None,
            region_name=settings.STATIC_DEPLOYMENT_S3_REGION,
        )
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.STATIC_DEPLOYMENT_S3_BUCKET):
            for item in page.get("Contents", []):
                objects.append({"key": item["Key"], "size": item.get("Size"), "etag": item.get("ETag"), "last_modified": item.get("LastModified").isoformat() if item.get("LastModified") else None})
    metadata_path.write_text(json.dumps({"bucket": settings.STATIC_DEPLOYMENT_S3_BUCKET, "objects": objects}, indent=2), encoding="utf-8")
    manifest["components"]["s3_metadata"] = {"path": "s3/objects.json", "object_count": len(objects), "sha256": _sha256_file(metadata_path)}


def _backup_deployment_files(payload_dir, manifest):
    target = payload_dir / "deployment_files"
    target.mkdir()
    copied = 0
    mode = "local"
    if settings.STATIC_DEPLOYMENT_STORAGE_BACKEND == "s3" and settings.STATIC_DEPLOYMENT_S3_BUCKET:
        import boto3

        mode = "s3"
        client = boto3.client(
            "s3",
            endpoint_url=settings.STATIC_DEPLOYMENT_S3_ENDPOINT_URL or None,
            region_name=settings.STATIC_DEPLOYMENT_S3_REGION,
        )
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.STATIC_DEPLOYMENT_S3_BUCKET):
            for item in page.get("Contents", []):
                key = item["Key"]
                destination = _safe_backup_child_path(target, key)
                destination.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(settings.STATIC_DEPLOYMENT_S3_BUCKET, key, str(destination))
                copied += 1
    else:
        source = Path(settings.STATIC_DEPLOYMENT_LOCAL_ROOT)
        for file_path in source.rglob("*"):
            if file_path.is_file():
                relative = file_path.relative_to(source)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, destination)
                copied += 1
    manifest["components"]["deployment_files"] = {"path": "deployment_files", "file_count": copied, "mode": mode}


def _backup_platform_config(payload_dir, manifest):
    target = payload_dir / "config"
    target.mkdir()
    values = {key: os.environ.get(key, "") for key in settings.BACKUP_PLATFORM_CONFIG_KEYS}
    path = target / "platform-config.json"
    path.write_text(json.dumps(values, indent=2, sort_keys=True), encoding="utf-8")
    manifest["components"]["platform_config"] = {"path": "config/platform-config.json", "keys": sorted(values.keys()), "sha256": _sha256_file(path)}


def _backup_secret_fingerprints(payload_dir, manifest):
    target = payload_dir / "secrets"
    target.mkdir()
    fingerprints = {}
    for key in settings.BACKUP_SECRET_FINGERPRINT_KEYS:
        value = os.environ.get(key)
        fingerprints[key] = _secret_fingerprint(value) if value else None
    path = target / "secret-fingerprints.json"
    path.write_text(json.dumps(fingerprints, indent=2, sort_keys=True), encoding="utf-8")
    manifest["components"]["secret_fingerprints"] = {"path": "secrets/secret-fingerprints.json", "keys": sorted(fingerprints.keys()), "sha256": _sha256_file(path)}


def _apply_retention(output_dir, retention_days):
    if retention_days <= 0:
        return
    cutoff = timezone.now() - timedelta(days=retention_days)
    for path in output_dir.glob("*.tar.gz.enc"):
        modified_at = timezone.datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())
        if modified_at < cutoff:
            path.unlink(missing_ok=True)
            checksum = path.with_suffix("").with_suffix("").with_suffix(".sha256")
            checksum.unlink(missing_ok=True)


def _safe_extract_tar(archive_path, destination):
    destination = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise BackupError("Backup archive contains a link entry.")
            target = (destination / member.name).resolve()
            try:
                target.relative_to(destination)
            except ValueError:
                raise BackupError("Unsafe path in backup archive.")
        archive.extractall(destination)


def _safe_backup_child_path(root, relative_name):
    child = (root / relative_name).resolve()
    try:
        child.relative_to(root.resolve())
    except ValueError as exc:
        raise BackupError("Unsafe object key in backup source.") from exc
    return child


def _require_encryption_key(encryption_key=None):
    key = encryption_key or settings.BACKUP_ENCRYPTION_KEY
    if not key:
        raise BackupError("BACKUP_ENCRYPTION_KEY is required.")
    return key


def _fernet(key):
    try:
        return Fernet(key.encode("ascii") if isinstance(key, str) else key)
    except ValueError:
        material = hashlib.sha256(str(key).encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(material))


def _secret_fingerprint(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()
