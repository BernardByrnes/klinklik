"""Run the explicit MIG-002 QueueEntry reconciliation phases."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.migration_reconciliation import (
    backfill_mig002,
    constrain_mig002,
    cutover_mig002,
    expand_mig002,
    inventory_mig002,
    resolve_mig002_reconciliation,
    rollback_mig002,
    verify_mig002,
)
from core.services import tenant_atomic
from tenancy.models import Facility, Organisation
from accounts.models import User, UserFacilityRole


class Command(BaseCommand):
    help = "Run an explicit MIG-002 QueueEntry expand/inventory/backfill/reconcile/verify/cutover/constrain phase."

    def add_arguments(self, parser):
        parser.add_argument(
            "phase",
            choices=("expand", "inventory", "backfill", "reconcile", "verify", "cutover", "constrain", "rollback"),
        )
        parser.add_argument("--organisation", required=True, help="Organisation UUID.")
        parser.add_argument("--facility", help="Optional facility UUID for inventory/backfill/verify.")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--after-id", help="Resume backfill after this stable QueueEntry UUID.")
        parser.add_argument("--reason", help="Required rollback reason.")
        parser.add_argument("--reconciliation-id", help="MigrationReconciliation UUID for reconcile.")
        parser.add_argument("--actor", help="Authorised user UUID for reconcile.")

    def handle(self, *args, **options):
        organisation = Organisation.objects.filter(id=options["organisation"]).first()
        if organisation is None:
            raise CommandError("The organisation was not found.")
        facility_id = options.get("facility")

        phase = options["phase"]
        with tenant_atomic(organisation.id):
            if facility_id and not Facility.objects.filter(
                id=facility_id,
                organisation=organisation,
                is_active=True,
            ).exists():
                raise CommandError("The facility was not found in this organisation.")
            if phase == "inventory":
                result = inventory_mig002(organisation=organisation, facility_id=facility_id)
            elif phase == "expand":
                result = expand_mig002(organisation=organisation)
            elif phase == "backfill":
                result = backfill_mig002(
                    organisation=organisation,
                    facility_id=facility_id,
                    batch_size=options["batch_size"],
                    after_id=options.get("after_id"),
                )
            elif phase == "verify":
                result = verify_mig002(organisation=organisation, facility_id=facility_id)
            elif phase == "reconcile":
                if not options.get("reconciliation_id") or not options.get("reason") or not options.get("actor"):
                    raise CommandError("--reconciliation-id, --actor, and --reason are required for reconcile.")
                actor = User.objects.filter(id=options["actor"], is_active=True).first()
                if actor is None or not UserFacilityRole.objects.filter(
                    organisation=organisation,
                    user=actor,
                    status="ACTIVE",
                ).exists():
                    raise CommandError("The reconcile actor was not found in this organisation.")
                try:
                    result = resolve_mig002_reconciliation(
                        organisation=organisation,
                        reconciliation_id=options["reconciliation_id"],
                        actor=actor,
                        reason=options["reason"],
                    )
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
            elif phase == "cutover":
                try:
                    result = cutover_mig002(organisation=organisation, facility_id=facility_id)
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
            elif phase == "constrain":
                try:
                    result = constrain_mig002(organisation=organisation)
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
            else:
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                try:
                    result = rollback_mig002(organisation=organisation, reason=options["reason"])
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc

        if phase == "reconcile":
            payload = {
                "migration_id": "MIG-002",
                "phase": "RECONCILE",
                "reconciliation_id": str(result.id),
                "resolution_state": result.resolution_state,
            }
        else:
            payload = result.as_dict() if hasattr(result, "as_dict") else {
                "phase": result.phase,
                "target_reads_enabled": result.target_reads_enabled,
                "target_writes_enabled": result.target_writes_enabled,
            }
        self.stdout.write(json.dumps(payload, sort_keys=True, default=str))
