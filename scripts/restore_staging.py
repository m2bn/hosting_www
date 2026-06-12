import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Verify and extract an encrypted platform backup into staging restore storage.")
    parser.add_argument("backup_path")
    parser.add_argument("--restore-dir", required=True)
    parser.add_argument("--confirm-staging", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
    import django

    django.setup()

    from apps.api.backups import BackupError, restore_to_staging

    try:
        result = restore_to_staging(
            encrypted_path=args.backup_path,
            restore_dir=args.restore_dir,
            confirm_staging=args.confirm_staging,
        )
    except BackupError as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1
    print(f"backup_id={result.backup_id}")
    print("restore_check=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
