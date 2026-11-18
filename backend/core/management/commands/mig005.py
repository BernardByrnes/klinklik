import json

from django.core.management.base import BaseCommand, CommandError

from core.mig005 import (
    MIGRATION_IDS,
    constrain_mig005,
    cutover_mig005,
    inventory_mig005,
    rollback_mig005,
    verify_mig005,
)
from core.services import tenant_atomic
from tenancy.models import Organisation


class Command(BaseCommand):
    help = "Run one explicit MIG-005..009 inventory/verify/constrain/cutover/rollback phase."

    def add_arguments(self, parser):
        parser.add_argument(
            "phase",
            choices=["inventory", "verify", "constrain", "cutover", "rollback"],
        )
        parser.add_argument("--organisation", required=True)
        parser.add_argument("--migration", required=True, choices=MIGRATION_IDS)
        parser.add_argument("--reason")

    def handle(self, *args, **options):
        organisation = Organisation.objects.filter(id=options["organisation"]).first()
        if organisation is None:
            raise CommandError("Organisation was not found.")
        phase = options["phase"]
        migration_id = options["migration"]
        with tenant_atomic(organisation.id):
            if phase == "inventory":
                result = inventory_mig005(
                    organisation=organisation, migration_id=migration_id
                )
            elif phase == "verify":
                result = verify_mig005(
                    organisation=organisation, migration_id=migration_id
                )
            elif phase == "constrain":
                result = constrain_mig005(
                    organisation=organisation, migration_id=migration_id
                )
            elif phase == "cutover":
                result = cutover_mig005(
                    organisation=organisation, migration_id=migration_id
                )
            else:
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                result = rollback_mig005(
                    organisation=organisation,
                    migration_id=migration_id,
                    reason=options["reason"],
                )
        self.stdout.write(json.dumps(result, sort_keys=True))
