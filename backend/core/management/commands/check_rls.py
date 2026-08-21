from django.core.management.base import BaseCommand
from core.rls import rls_status


class Command(BaseCommand):
    help = "Report whether the configured PostgreSQL tables have FORCE RLS enabled."

    def handle(self, *args, **options):
        status = rls_status()
        self.stdout.write(str(status))
        if status["backend"] == "postgresql" and not status["enforced"]:
            raise SystemExit(1)
