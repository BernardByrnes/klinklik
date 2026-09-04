import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from core.migration_reconciliation import (
    backfill_mig001,
    cutover_mig001,
    inventory_mig001,
    rollback_mig001,
    verify_mig001,
)
from core.services import tenant_atomic
from tenancy.models import Organisation


class Command(BaseCommand):
    help = "Run one explicit MIG-001 expand/backfill/verify/cutover/rollback phase."

    def add_arguments(self, parser):
        parser.add_argument("phase", choices=["inventory", "backfill", "verify", "cutover", "rollback"])
        parser.add_argument("--organisation", required=True)
        parser.add_argument("--facility")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--after-id")
        parser.add_argument("--run-id")
        parser.add_argument("--reason")

    def handle(self, *args, **options):
        organisation = Organisation.objects.filter(id=options["organisation"]).first()
        if organisation is None:
            raise CommandError("Organisation was not found.")
        phase = options["phase"]
        run_id = options.get("run_id")
        if run_id:
            try:
                run_id = UUID(run_id)
            except (TypeError, ValueError) as exc:
                raise CommandError("--run-id must be a valid UUID.") from exc
        with tenant_atomic(organisation.id):
            kwargs = {"organisation": organisation, "facility_id": options.get("facility")}
            if phase == "inventory":
                result = inventory_mig001(**kwargs)
            elif phase == "backfill":
                result = backfill_mig001(
                    **kwargs,
                    batch_size=options["batch_size"],
                    after_id=options.get("after_id"),
                    run_id=run_id,
                )
            elif phase == "verify":
                result = verify_mig001(**kwargs)
            elif phase == "cutover":
                result = cutover_mig001(**kwargs)
            else:
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                result = rollback_mig001(
                    organisation=organisation,
                    reason=options["reason"],
                )
                result = {"migration_id": "MIG-001", "phase": result.phase, "target_reads_enabled": result.target_reads_enabled, "target_writes_enabled": result.target_writes_enabled}
        self.stdout.write(json.dumps(result.as_dict() if hasattr(result, "as_dict") else result, sort_keys=True))
