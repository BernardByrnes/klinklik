from django.core.management.base import BaseCommand
from core.rls import rls_status


class Command(BaseCommand):
    help = "Report whether the configured PostgreSQL tables have FORCE RLS enabled."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-postgres",
            action="store_true",
            help="Fail when the configured database is not PostgreSQL.",
        )

    def handle(self, *args, **options):
        status = rls_status()
        self.stdout.write(str(status))
        if options["require_postgres"] and status["backend"] != "postgresql":
            raise SystemExit(1)
        if status["backend"] == "postgresql" and not status["enforced"]:
            raise SystemExit(1)
