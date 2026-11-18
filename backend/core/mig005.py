"""MIG-005..009 scoped reconciliation for cashier financial evidence.

The five migrations share one evidence engine but keep separate cutover rows
and blocker checks:

* MIG-005: Invoice gross/applied/outstanding parity under the target equations.
* MIG-006: legacy POSTED payments mapped to CONFIRMED with actor/time evidence.
* MIG-007: compatibility invoice reference valid for single-invoice payments.
* MIG-008: exact effective allocation evidence for every confirmed payment.
* MIG-009: one receipt identity per payment with deterministic content hash.
"""

import hashlib
from decimal import Decimal
from uuid import uuid4

from django.db import models

from billing.models import (
    Invoice,
    Payment,
    PaymentAllocation,
    PaymentReceipt,
)
from core.clock import now
from core.idempotency import canonical_json
from core.models import MigrationCutover, MigrationReconciliation
from core.services import assert_transaction_active

MIGRATION_IDS = ("MIG-005", "MIG-006", "MIG-007", "MIG-008", "MIG-009")


def _validate(migration_id):
    if migration_id not in MIGRATION_IDS:
        raise ValueError("Unknown S-05 migration id: " + str(migration_id))


def _digest(rows):
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()


def _receipt_hash(payment, allocations):
    envelope = {
        "payment_id": str(payment.id),
        "receipt_no": payment.receipt_no,
        "amount": str(payment.amount),
        "method": payment.method,
        "received_at": payment.received_at.isoformat(),
        "allocations": [
            {"invoice_id": str(allocation.invoice_id), "amount": str(allocation.amount)}
            for allocation in allocations
        ],
    }
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()


def _cutover(organisation, migration_id):
    cutover, _created = MigrationCutover.objects.get_or_create(
        organisation=organisation, migration_id=migration_id
    )
    return cutover


def _exception(organisation, migration_id, table, pk, codes, source_hash="", proposed=None):
    evidence, _created = MigrationReconciliation.objects.get_or_create(
        organisation=organisation,
        migration_id=migration_id,
        legacy_table=table,
        legacy_pk=str(pk),
        defaults={
            "evidence_codes": list(codes),
            "source_hash": source_hash,
            "target_hash": "",
            "proposed_target_refs": proposed or None,
        },
    )
    return evidence


def _invoice_rows(organisation):
    rows = []
    for invoice in Invoice.objects.filter(organisation=organisation).order_by("id").iterator():
        if invoice.status in {"VOID", "VOIDED"}:
            rows.append({"id": str(invoice.id), "status": invoice.status})
            continue
        subtotal = sum(
            (
                line.amount
                for line in invoice.items.filter(state="ACTIVE")
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        discount = min(invoice.discount, subtotal).quantize(Decimal("0.01"))
        total = (subtotal - discount).quantize(Decimal("0.01"))
        applied = sum(
            (
                allocation.amount
                for allocation in PaymentAllocation.objects.filter(
                    invoice=invoice,
                    payment__status__in=Payment.EFFECTIVE_STATUSES,
                )
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        balance = max(Decimal("0.00"), total - applied).quantize(Decimal("0.01"))
        stored = {
            "subtotal": invoice.subtotal,
            "total": invoice.total,
            "amount_paid": invoice.amount_paid,
            "balance": invoice.balance,
        }
        computed = {
            "subtotal": subtotal,
            "total": total,
            "amount_paid": applied,
            "balance": balance,
        }
        rows.append(
            {
                "id": str(invoice.id),
                "status": invoice.status,
                "stored": {key: str(value) for key, value in stored.items()},
                "computed": {key: str(value) for key, value in computed.items()},
                "match": stored == computed,
            }
        )
    return rows


def _payment_rows(organisation):
    rows = []
    for payment in Payment.objects.filter(organisation=organisation).order_by("id").iterator():
        allocations = list(payment.allocations.order_by("invoice_id"))
        rows.append(
            {
                "id": str(payment.id),
                "status": payment.status,
                "amount": str(payment.amount),
                "invoice_id": str(payment.invoice_id) if payment.invoice_id else None,
                "allocation_count": len(allocations),
                "allocation_total": str(
                    sum((allocation.amount for allocation in allocations), Decimal("0.00"))
                ),
                "allocations": [
                    {
                        "invoice_id": str(allocation.invoice_id),
                        "amount": str(allocation.amount),
                        "in_scope": (
                            allocation.organisation_id == payment.organisation_id
                            and allocation.facility_id == payment.facility_id
                        ),
                    }
                    for allocation in allocations
                ],
                "receipt_count": PaymentReceipt.objects.filter(payment=payment).count(),
                "has_actor": payment.received_by_id is not None,
                "has_time": payment.received_at is not None,
            }
        )
    return rows


def _scan(organisation, migration_id):
    invoice_rows = _invoice_rows(organisation)
    payment_rows = _payment_rows(organisation)
    issues = []
    if migration_id == "MIG-005":
        evidence = invoice_rows
        for row in invoice_rows:
            if row["status"] in {"VOID", "VOIDED"}:
                continue
            if not row["match"]:
                issues.append((row["id"], ("PROJECTION_MISMATCH",), _digest(row)))
        source_count = len(invoice_rows)
    elif migration_id == "MIG-006":
        evidence = payment_rows
        for row in payment_rows:
            if row["status"] not in {"CONFIRMED", "REVERSED"}:
                issues.append((row["id"], ("LEGACY_PAYMENT_STATUS",), _digest(row)))
            elif not row["has_actor"] or not row["has_time"]:
                issues.append((row["id"], ("PAYMENT_PROVENANCE_MISSING",), _digest(row)))
        source_count = len(payment_rows)
    elif migration_id == "MIG-007":
        evidence = payment_rows
        for row in payment_rows:
            if row["allocation_count"] == 1:
                if row["invoice_id"] != row["allocations"][0]["invoice_id"]:
                    issues.append((row["id"], ("COMPAT_INVOICE_LINK_MISMATCH",), _digest(row)))
            elif row["allocation_count"] > 1 and row["invoice_id"] is not None:
                issues.append((row["id"], ("MULTI_INVOICE_COMPAT_LINK",), _digest(row)))
        source_count = len(payment_rows)
    elif migration_id == "MIG-008":
        evidence = payment_rows
        for row in payment_rows:
            if row["status"] not in Payment.EFFECTIVE_STATUSES:
                continue
            if row["allocation_count"] == 0:
                issues.append((row["id"], ("ALLOCATION_EVIDENCE_MISSING",), _digest(row)))
            elif Decimal(row["allocation_total"]) != Decimal(row["amount"]):
                issues.append((row["id"], ("ALLOCATION_SUM_MISMATCH",), _digest(row)))
            elif not all(item["in_scope"] for item in row["allocations"]):
                issues.append((row["id"], ("ALLOCATION_SCOPE_MISMATCH",), _digest(row)))
        source_count = len(payment_rows)
    else:
        evidence = payment_rows
        receipt_numbers = set()
        for payment in Payment.objects.filter(organisation=organisation).order_by("id"):
            receipt = PaymentReceipt.objects.filter(payment=payment).first()
            allocations = list(payment.allocations.order_by("invoice_id"))
            if receipt is None:
                issues.append((payment.id, ("RECEIPT_MISSING",), _digest(str(payment.id))))
                continue
            if receipt.receipt_no != payment.receipt_no:
                issues.append((payment.id, ("RECEIPT_NUMBER_MISMATCH",), receipt.content_hash))
            if allocations and receipt.content_hash != _receipt_hash(payment, allocations):
                issues.append((payment.id, ("RECEIPT_HASH_MISMATCH",), receipt.content_hash))
            if receipt.receipt_no in receipt_numbers:
                issues.append((payment.id, ("RECEIPT_NUMBER_REUSED",), receipt.content_hash))
            receipt_numbers.add(receipt.receipt_no)
        source_count = len(payment_rows)
    return {
        "source_count": source_count,
        "issues": issues,
        "digest": _digest(evidence),
        "evidence": evidence,
    }


def _facility_counts(rows):
    counts = {}
    for row in rows:
        key = row.get("facility_id") or "UNSCOPED"
        counts[key] = counts.get(key, 0) + 1
    return counts


def inventory_mig005(*, organisation, migration_id):
    _validate(migration_id)
    assert_transaction_active()
    cutover = _cutover(organisation, migration_id)
    scan = _scan(organisation, migration_id)
    cutover.inventory_completed_at = now()
    cutover.inventory_source_count = scan["source_count"]
    cutover.inventory_digest = scan["digest"]
    cutover.phase = "EXPANDED"
    cutover.version += 1
    cutover.save(
        update_fields=[
            "inventory_completed_at",
            "inventory_source_count",
            "inventory_digest",
            "phase",
            "version",
            "updated_at",
        ]
    )
    return {
        "migration_id": migration_id,
        "phase": cutover.phase,
        "source_count": scan["source_count"],
        "digest": scan["digest"],
        "issue_count": len(scan["issues"]),
    }


def verify_mig005(*, organisation, migration_id):
    _validate(migration_id)
    assert_transaction_active()
    cutover = _cutover(organisation, migration_id)
    scan = _scan(organisation, migration_id)
    for pk, codes, source_hash in scan["issues"]:
        _exception(
            organisation,
            migration_id,
            "billing_payment" if migration_id != "MIG-005" else "billing_invoice",
            pk,
            codes,
            source_hash=source_hash,
        )
    pending = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=migration_id, resolution_state="PENDING"
    ).count()
    previous_passes = cutover.parity_passes if cutover.parity_digest == scan["digest"] else 0
    clean = not scan["issues"] and pending == 0
    cutover.parity_digest = scan["digest"]
    cutover.parity_passes = (previous_passes + 1) if clean else 0
    cutover.last_verified_at = now()
    cutover.stable_full_scan_count = cutover.parity_passes
    cutover.blocker_checks_passed = clean and cutover.parity_passes >= 2
    cutover.phase = "VERIFIED" if clean else "BLOCKED"
    cutover.version += 1
    cutover.save(
        update_fields=[
            "parity_digest",
            "parity_passes",
            "last_verified_at",
            "stable_full_scan_count",
            "blocker_checks_passed",
            "phase",
            "version",
            "updated_at",
        ]
    )
    return {
        "migration_id": migration_id,
        "phase": cutover.phase,
        "source_count": scan["source_count"],
        "issue_count": len(scan["issues"]),
        "pending_reconciliations": pending,
        "parity_passes": cutover.parity_passes,
        "blocker_checks_passed": cutover.blocker_checks_passed,
        "digest": scan["digest"],
    }


def constrain_mig005(*, organisation, migration_id):
    _validate(migration_id)
    assert_transaction_active()
    cutover = _cutover(organisation, migration_id)
    if cutover.parity_passes < 2 or not cutover.blocker_checks_passed:
        raise ValueError(
            f"{migration_id} requires two stable clean scans before CONSTRAINED."
        )
    pending = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=migration_id, resolution_state="PENDING"
    ).exists()
    if pending:
        raise ValueError(f"{migration_id} has unresolved reconciliation evidence.")
    cutover.phase = "CONSTRAINED"
    cutover.version += 1
    cutover.save(update_fields=["phase", "version", "updated_at"])
    return {"migration_id": migration_id, "phase": cutover.phase}


def cutover_mig005(*, organisation, migration_id):
    _validate(migration_id)
    assert_transaction_active()
    cutover = _cutover(organisation, migration_id)
    if cutover.phase != "CONSTRAINED":
        raise ValueError(f"{migration_id} must be CONSTRAINED before cutover.")
    cutover.phase = "CUTOVER"
    cutover.target_reads_enabled = True
    cutover.target_writes_enabled = True
    cutover.write_fence += 1
    cutover.version += 1
    cutover.save(
        update_fields=[
            "phase",
            "target_reads_enabled",
            "target_writes_enabled",
            "write_fence",
            "version",
            "updated_at",
        ]
    )
    return {
        "migration_id": migration_id,
        "phase": cutover.phase,
        "target_reads_enabled": cutover.target_reads_enabled,
        "target_writes_enabled": cutover.target_writes_enabled,
    }


def rollback_mig005(*, organisation, migration_id, reason):
    _validate(migration_id)
    assert_transaction_active()
    if not (reason or "").strip():
        raise ValueError("A rollback reason is required.")
    cutover = _cutover(organisation, migration_id)
    cutover.phase = "EXPANDED"
    cutover.target_reads_enabled = False
    cutover.target_writes_enabled = False
    cutover.write_fence += 1
    cutover.rollback_at = now()
    cutover.rollback_reason = reason.strip()[:240]
    cutover.version += 1
    cutover.save(
        update_fields=[
            "phase",
            "target_reads_enabled",
            "target_writes_enabled",
            "write_fence",
            "rollback_at",
            "rollback_reason",
            "version",
            "updated_at",
        ]
    )
    return {
        "migration_id": migration_id,
        "phase": cutover.phase,
        "target_reads_enabled": cutover.target_reads_enabled,
        "target_writes_enabled": cutover.target_writes_enabled,
        "rollback_at": cutover.rollback_at.isoformat(),
    }
