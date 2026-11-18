import json

from django.core.management.base import BaseCommand, CommandError

from core.mig010 import (
    constrain_mig010,
    cutover_mig010,
    inventory_mig010,
    rollback_mig010,
    verify_mig010,
)
from core.services import tenant_atomic
from tenancy.models import Organisation


class Command(BaseCommand):
    help = "Run one explicit MIG-010 inventory/verify/constrain/cutover/rollback phase."

    def add_arguments(self, parser):
        parser.add_argument(
            "phase", choices=["inventory", "verify", "constrain", "cutover", "rollback"]
        )
        parser.add_argument("--organisation", required=True)
        parser.add_argument("--reason")

    def handle(self, *args, **options):
        organisation = Organisation.objects.filter(id=options["organisation"]).first()
        if organisation is None:
            raise CommandError("Organisation was not found.")
        phase = options["phase"]
        with tenant_atomic(organisation.id):
            if phase == "inventory":
                result = inventory_mig010(organisation=organisation)
            elif phase == "verify":
                result = verify_mig010(organisation=organisation)
            elif phase == "constrain":
                result = constrain_mig010(organisation=organisation)
            elif phase == "cutover":
                result = cutover_mig010(organisation=organisation)
            else:
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                result = rollback_mig010(
                    organisation=organisation, reason=options["reason"]
                )
        self.stdout.write(json.dumps(result, sort_keys=True))
