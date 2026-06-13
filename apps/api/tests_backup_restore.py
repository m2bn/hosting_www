import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.api.backups import BackupError, create_backup, restore_to_staging, verify_backup, _safe_extract_tar


class BackupRestoreTests(TestCase):
    def setUp(self):
        self.encryption_key = Fernet.generate_key().decode("ascii")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "backups"
        self.deployment_root = self.root / "deployments"
        self.deployment_root.mkdir()
        (self.deployment_root / "org" / "project").mkdir(parents=True)
        (self.deployment_root / "org" / "project" / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")

    @override_settings(
        BACKUP_PLATFORM_CONFIG_KEYS=["DJANGO_ALLOWED_HOSTS"],
        BACKUP_SECRET_FINGERPRINT_KEYS=["DJANGO_SECRET_KEY", "STRIPE_SECRET_KEY"],
    )
    def test_backup_is_encrypted_and_restore_check_passes(self):
        with self._backup_settings(), self._env(DJANGO_SECRET_KEY="super-secret", STRIPE_SECRET_KEY="sk_test_secret"):
            result = create_backup(output_dir=self.output_dir, encryption_key=self.encryption_key, retention_days=30)

        self.assertTrue(result.encrypted_path.exists())
        with self.assertRaises((InvalidToken, UnicodeDecodeError, tarfile.TarError)):
            tarfile.open(result.encrypted_path, "r:gz")

        check = verify_backup(encrypted_path=result.encrypted_path, encryption_key=self.encryption_key)
        self.assertTrue(check.ok)
        self.assertEqual(check.backup_id, result.backup_id)

    @override_settings(
        BACKUP_PLATFORM_CONFIG_KEYS=["DJANGO_ALLOWED_HOSTS"],
        BACKUP_SECRET_FINGERPRINT_KEYS=["DJANGO_SECRET_KEY", "STRIPE_SECRET_KEY"],
    )
    def test_restore_to_staging_extracts_payload_without_logging_plaintext_secrets(self):
        with self._backup_settings(), self._env(DJANGO_SECRET_KEY="super-secret", STRIPE_SECRET_KEY="sk_test_secret", APP_ENV="staging"):
            result = create_backup(output_dir=self.output_dir, encryption_key=self.encryption_key, retention_days=30)
            restore_dir = self.root / "restore"
            check = restore_to_staging(encrypted_path=result.encrypted_path, restore_dir=restore_dir, encryption_key=self.encryption_key)

        self.assertTrue(check.ok)
        manifest_path = restore_dir / "payload" / "manifest.json"
        secrets_path = restore_dir / "payload" / "secrets" / "secret-fingerprints.json"
        self.assertTrue(manifest_path.exists())
        secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
        self.assertNotIn("super-secret", json.dumps(secrets))
        self.assertNotIn("sk_test_secret", json.dumps(secrets))
        self.assertRegex(secrets["DJANGO_SECRET_KEY"], r"^[0-9a-f]{16}$")

    def test_restore_refuses_production(self):
        with self._backup_settings():
            result = create_backup(output_dir=self.output_dir, encryption_key=self.encryption_key, retention_days=30)
            with self.assertRaises(BackupError):
                restore_to_staging(
                    encrypted_path=result.encrypted_path,
                    restore_dir=self.root / "restore",
                    encryption_key=self.encryption_key,
                    target_environment="production",
                )

    def test_management_command_documents_restore_verification(self):
        with self._backup_settings():
            result = create_backup(output_dir=self.output_dir, encryption_key=self.encryption_key, retention_days=30)
            call_command("test_restore_backup", str(result.encrypted_path))
            with self.assertRaises(CommandError):
                call_command("test_restore_backup", str(result.encrypted_path), execute=True, restore_dir=str(self.root / "restore"))

    @override_settings(
        STATIC_DEPLOYMENT_STORAGE_BACKEND="s3",
        STATIC_DEPLOYMENT_S3_BUCKET="deployment-backups",
        STATIC_DEPLOYMENT_S3_ENDPOINT_URL="http://minio.local",
        STATIC_DEPLOYMENT_S3_REGION="us-east-1",
    )
    def test_s3_backup_rejects_object_keys_outside_backup_payload(self):
        paginator = Mock()
        paginator.paginate.return_value = [{"Contents": [{"Key": "../escape.txt", "Size": 1, "ETag": "etag"}]}]
        client = Mock()
        client.get_paginator.return_value = paginator

        boto3_stub = SimpleNamespace(client=Mock(return_value=client))
        with patch.dict(sys.modules, {"boto3": boto3_stub}):
            with self.assertRaises(BackupError):
                create_backup(output_dir=self.output_dir, encryption_key=self.encryption_key, retention_days=30)

    def test_restore_rejects_tar_link_entries(self):
        archive_path = self.root / "malicious.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            info = tarfile.TarInfo("payload/link")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside"
            archive.addfile(info)

        with self.assertRaises(BackupError):
            _safe_extract_tar(archive_path, self.root / "restore-links")

    def _backup_settings(self):
        return override_settings(
            BACKUP_ENCRYPTION_KEY=self.encryption_key,
            BACKUP_OUTPUT_DIR=str(self.output_dir),
            STATIC_DEPLOYMENT_STORAGE_BACKEND="local",
            STATIC_DEPLOYMENT_LOCAL_ROOT=str(self.deployment_root),
        )

    def _env(self, **values):
        class EnvOverride:
            def __enter__(inner_self):
                inner_self.previous = {key: os.environ.get(key) for key in values}
                os.environ.update(values)

            def __exit__(inner_self, exc_type, exc, traceback):
                for key, previous in inner_self.previous.items():
                    if previous is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = previous

        return EnvOverride()
