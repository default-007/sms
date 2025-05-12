# src/core/management/commands/init_settings.py
from django.core.management.base import BaseCommand
from src.core.services import SystemSettingService


class Command(BaseCommand):
    help = "Initialize default system settings"

    def handle(self, *args, **options):
        self.stdout.write("Initializing default system settings...")
        SystemSettingService.initialize_default_settings()
        self.stdout.write(
            self.style.SUCCESS("System settings initialized successfully.")
        )
