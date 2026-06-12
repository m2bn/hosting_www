from django.core.management.base import BaseCommand, CommandError

from apps.api.backups import BackupError, restore_to_staging, verify_backup


class Command(BaseCommand):
    help = "Verify an encrypted backup and optionally extract it into a staging restore directory."

    def add_arguments(self, parser):
        parser.add_argument("backup_path")
        parser.add_argument("--restore-dir", default="")
        parser.add_argument("--execute", action="store_true", help="Extract backup payload into --restore-dir after verification.")
        parser.add_argument("--confirm-staging", action="store_true", help="Required when APP_ENV is not staging.")

    def handle(self, *args, **options):
        try:
            if options["execute"]:
                if not options["restore_dir"]:
                    raise CommandError("--restore-dir is required with --execute.")
                result = restore_to_staging(
                    encrypted_path=options["backup_path"],
                    restore_dir=options["restore_dir"],
                    confirm_staging=options["confirm_staging"],
                )
            else:
                result = verify_backup(encrypted_path=options["backup_path"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        for check in result.checks:
            status = "ok" if check["ok"] else "failed"
            self.stdout.write(f"{check['name']}: {status}")
        if not result.ok:
            raise CommandError("Backup restore verification failed.")
        self.stdout.write(self.style.SUCCESS(f"Backup {result.backup_id} restore verification passed."))
