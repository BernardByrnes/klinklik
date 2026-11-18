"""Run the explicit MIG-003 versioned-triage reconciliation phases."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.mig003 import (
    backfill_mig003,
    constrain_mig003,
    cutover_mig003,
    inventory_mig003,
    rollback_mig003,
    verify_mig003,
)
from core.services import tenant_atomic
from tenancy.models import Facility, Organisation


class Command(BaseCommand):
    help = "Run an explicit MIG-003 triage inventory/backfill/verify/constrain/cutover/rollback phase."

    def add_arguments(self, parser):
        parser.add_argument(
            "phase",
            choices=("inventory", "backfill", "verify", "cutover", "constrain", "rollback"),
        )
        parser.add_argument("--organisation", required=True, help="Organisation UUID.")
        parser.add_argument("--facility", help="Optional facility UUID for inventory/backfill/verify.")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--after-id", help="Resume backfill after this stable TriageAssessment UUID.")
        parser.add_argument("--reason", help="Required rollback reason.")

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
                result = inventory_mig003(
                    organisation=organisation, facility_id=facility_id
                )
            elif phase == "backfill":
                result = backfill_mig003(
                    organisation=organisation,
                    facility_id=facility_id,
                    batch_size=options["batch_size"],
                    after_id=options.get("after_id"),
                )
            elif phase == "verify":
                result = verify_mig003(
                    organisation=organisation, facility_id=facility_id
                )
            elif phase == "constrain":
                try:
                    result = constrain_mig003(organisation=organisation)
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
            elif phase == "cutover":
                try:
                    result = cutover_mig003(organisation=organisation)
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc
            else:
                if not options.get("reason"):
                    raise CommandError("--reason is required for rollback.")
                try:
                    result = rollback_mig003(
                        organisation=organisation, reason=options["reason"]
                    )
                except ValueError as exc:
                    raise CommandError(str(exc)) from exc

        payload = result.as_dict() if hasattr(result, "as_dict") else {
            "phase": result.phase,
            "target_reads_enabled": result.target_reads_enabled,
            "target_writes_enabled": result.target_writes_enabled,
        }
        self.stdout.write(json.dumps(payload, sort_keys=True, default=str))
