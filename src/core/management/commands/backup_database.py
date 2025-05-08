# management/commands/backup_database.py
from django.core.management.base import BaseCommand
import subprocess
import os
import datetime
import pathlib


class Command(BaseCommand):
    help = "Create a database backup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="backups",
            help="Directory where backups will be stored",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        # Get database settings
        db_settings = settings.DATABASES["default"]
        engine = db_settings["ENGINE"]

        # Get timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create output directory if it doesn't exist
        output_dir = options["output_dir"]
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Handle different database engines
        if "postgresql" in engine:
            self._backup_postgresql(db_settings, output_dir, timestamp)
        elif "mysql" in engine:
            self._backup_mysql(db_settings, output_dir, timestamp)
        elif "sqlite3" in engine:
            self._backup_sqlite(db_settings, output_dir, timestamp)
        else:
            self.stderr.write(
                self.style.ERROR(f"Unsupported database engine: {engine}")
            )

    def _backup_postgresql(self, db_settings, output_dir, timestamp):
        db_name = db_settings["NAME"]
        db_user = db_settings["USER"]
        db_host = db_settings.get("HOST", "localhost")
        db_port = db_settings.get("PORT", "5432")

        # Build output file path
        output_file = os.path.join(
            output_dir, f"backup_postgres_{db_name}_{timestamp}.sql"
        )

        # Build pg_dump command
        cmd = [
            "pg_dump",
            "-h",
            db_host,
            "-p",
            db_port,
            "-U",
            db_user,
            "-d",
            db_name,
            "-f",
            output_file,
        ]

        # Set environment variables for password
        env = os.environ.copy()
        if "PASSWORD" in db_settings:
            env["PGPASSWORD"] = db_settings["PASSWORD"]

        try:
            self.stdout.write(f"Creating PostgreSQL backup to {output_file}...")
            subprocess.run(cmd, env=env, check=True)
            self.stdout.write(
                self.style.SUCCESS(f"Backup completed successfully: {output_file}")
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))

    def _backup_mysql(self, db_settings, output_dir, timestamp):
        db_name = db_settings["NAME"]
        db_user = db_settings["USER"]
        db_host = db_settings.get("HOST", "localhost")
        db_port = db_settings.get("PORT", "3306")

        # Build output file path
        output_file = os.path.join(
            output_dir, f"backup_mysql_{db_name}_{timestamp}.sql"
        )

        # Build mysqldump command
        cmd = [
            "mysqldump",
            "-h",
            db_host,
            "-P",
            db_port,
            "-u",
            db_user,
            db_name,
            "-r",
            output_file,
        ]

        # Add password if provided
        if "PASSWORD" in db_settings and db_settings["PASSWORD"]:
            cmd.extend(["-p", db_settings["PASSWORD"]])

        try:
            self.stdout.write(f"Creating MySQL backup to {output_file}...")
            subprocess.run(cmd, check=True)
            self.stdout.write(
                self.style.SUCCESS(f"Backup completed successfully: {output_file}")
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))

    def _backup_sqlite(self, db_settings, output_dir, timestamp):
        import shutil

        db_path = db_settings["NAME"]

        # Check if database file exists
        if not os.path.exists(db_path):
            self.stderr.write(
                self.style.ERROR(f"SQLite database file not found: {db_path}")
            )
            return

        # Build output file path
        output_file = os.path.join(
            output_dir, f"backup_sqlite_{os.path.basename(db_path)}_{timestamp}.sqlite"
        )

        try:
            self.stdout.write(f"Copying SQLite database to {output_file}...")
            shutil.copy2(db_path, output_file)
            self.stdout.write(
                self.style.SUCCESS(f"Backup completed successfully: {output_file}")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))
