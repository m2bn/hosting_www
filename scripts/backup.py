import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    import django

    django.setup()

    from apps.api.backups import BackupError, create_backup

    try:
        result = create_backup()
    except BackupError as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"backup_id={result.backup_id}")
    print(f"path={result.encrypted_path}")
    print(f"sha256={result.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
