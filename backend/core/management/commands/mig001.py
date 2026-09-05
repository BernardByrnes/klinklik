import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from core.migration_reconciliation import (
    backfill_mig001,
    cutover_mig001,
    inventory_mig001,
    resolve_reconciliation,
    rollback_mig001,
    verify_mig001,
)
from core.services import tenant_atomic
from accounts.models import User
from tenancy.models import Organisation


class Command(BaseCommand):
    help = "Run one explicit MIG-001 expand/backfill/verify/cutover/rollback phase."

    def add_arguments(self, parser):
        parser.add_argument(
            "phase",
            choices=["inventory", "backfill", "verify", "cutover", "rollback", "resolve"],
        )
        parser.add_argument("--organisation", required=True)
        parser.add_argument("--facility")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--after-id")
        parser.add_argument("--run-id")
        parser.add_argument("--reconciliation")
        parser.add_argument("--actor")
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
                result = inventory_mig001(**kwargs, run_id=run_id)
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
            elif phase == "rollback":
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                result = rollback_mig001(
                    organisation=organisation,
                    reason=options["reason"],
                )
                result = {"migration_id": "MIG-001", "phase": result.phase, "target_reads_enabled": result.target_reads_enabled, "target_writes_enabled": result.target_writes_enabled}
            else:
                if not options.get("reconciliation"):
                    raise CommandError("--reconciliation is required for resolve.")
                if not options.get("actor"):
                    raise CommandError("--actor is required for resolve.")
                try:
                    reconciliation_id = UUID(options["reconciliation"])
                    actor_id = UUID(options["actor"])
                except (TypeError, ValueError) as exc:
                    raise CommandError("--reconciliation and --actor must be valid UUIDs.") from exc
                actor = User.objects.filter(
                    id=actor_id,
                    is_active=True,
                    memberships__organisation=organisation,
                    memberships__status="ACTIVE",
                ).first()
                if actor is None:
                    raise CommandError("The actor is not an active member of this organisation.")
                evidence = resolve_reconciliation(
                    organisation=organisation,
                    reconciliation_id=reconciliation_id,
                    actor=actor,
                    reason=options.get("reason") or "",
                )
                result = {
                    "migration_id": evidence.migration_id,
                    "evidence_id": str(evidence.id),
                    "resolution_state": evidence.resolution_state,
                    "source_hash": evidence.source_hash,
                    "target_hash": evidence.target_hash,
                    "backfill_run_id": str(evidence.backfill_run_id) if evidence.backfill_run_id else None,
                    "resolved_by": str(evidence.resolved_by_id) if evidence.resolved_by_id else None,
                }
        self.stdout.write(json.dumps(result.as_dict() if hasattr(result, "as_dict") else result, sort_keys=True))
