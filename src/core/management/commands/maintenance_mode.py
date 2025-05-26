# management/commands/maintenance_mode.py
from django.core.management.base import BaseCommand

from src.core.services import SystemSettingService


class Command(BaseCommand):
    help = "Enable or disable maintenance mode"

    def add_arguments(self, parser):
        parser.add_argument(
            "--enable",
            action="store_true",
            help="Enable maintenance mode",
        )
        parser.add_argument(
            "--disable",
            action="store_true",
            help="Disable maintenance mode",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Check maintenance mode status",
        )

    def handle(self, *args, **options):
        from src.core.utils import get_system_setting

        # Check if conflicting options
        if options["enable"] and options["disable"]:
            self.stderr.write(
                self.style.ERROR("Error: Cannot specify both --enable and --disable")
            )
            return

        # Get current status
        current_status = get_system_setting("maintenance_mode", False)

        # Just display status if requested
        if options["status"]:
            status_str = "ENABLED" if current_status else "DISABLED"
            self.stdout.write(f"Maintenance mode is currently {status_str}")
            return

        # Enable maintenance mode
        if options["enable"]:
            success, message = SystemSettingService.update_setting(
                "maintenance_mode", True
            )
            if success:
                self.stdout.write(
                    self.style.SUCCESS("Maintenance mode has been ENABLED")
                )
            else:
                self.stderr.write(
                    self.style.ERROR(f"Failed to enable maintenance mode: {message}")
                )
            return

        # Disable maintenance mode
        if options["disable"]:
            success, message = SystemSettingService.update_setting(
                "maintenance_mode", False
            )
            if success:
                self.stdout.write(
                    self.style.SUCCESS("Maintenance mode has been DISABLED")
                )
            else:
                self.stderr.write(
                    self.style.ERROR(f"Failed to disable maintenance mode: {message}")
                )
            return

        # If no options provided, show help
        self.stdout.write("Please specify an option: --enable, --disable, or --status")
