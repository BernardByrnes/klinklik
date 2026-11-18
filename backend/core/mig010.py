"""MIG-010 scoped reconciliation for introduced CreditNote/Refund records."""

import hashlib
from decimal import Decimal

from billing.models import CreditNote, Invoice, InvoiceItem, Payment, Refund
from core.clock import now
from core.idempotency import canonical_json
from core.models import MigrationCutover, MigrationReconciliation
from core.services import assert_transaction_active

MIGRATION_ID = "MIG-010"


def _digest(rows):
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()


def _exception(organisation, table, pk, codes, source_hash=""):
    return MigrationReconciliation.objects.get_or_create(
        organisation=organisation,
        migration_id=MIGRATION_ID,
        legacy_table=table,
        legacy_pk=str(pk),
        defaults={
            "evidence_codes": list(codes),
            "source_hash": source_hash,
            "target_hash": "",
        },
    )[0]


def _scan(organisation):
    issues = []
    rows = []
    suspicious = {
        "negative_invoice_lines": InvoiceItem.objects.filter(
            organisation=organisation, amount__lt=0
        ).count(),
        "nonpositive_payments": Payment.objects.filter(
            organisation=organisation, amount__lte=0
        ).count(),
        "unexplained_discounts": Invoice.objects.filter(
            organisation=organisation, discount__gt=0
        ).count(),
    }
    for invoice in Invoice.objects.filter(organisation=organisation).order_by("id"):
        credits = CreditNote.objects.filter(invoice=invoice, status="ISSUED")
        credit_total = sum((credit.amount for credit in credits), Decimal("0.00")).quantize(
            Decimal("0.01")
        )
        refunds = Refund.objects.filter(invoice=invoice, status="APPROVED")
        refunded_total = sum(
            (refund.amount for refund in refunds), Decimal("0.00")
        ).quantize(Decimal("0.01"))
        rows.append(
            {
                "invoice_id": str(invoice.id),
                "credit_total": str(invoice.credit_total),
                "refunded_total": str(invoice.refunded_total),
                "refundable_credit": str(invoice.refundable_credit),
                "credits": str(credit_total),
                "refunds": str(refunded_total),
                "credit_count": credits.count(),
                "refund_count": refunds.count(),
            }
        )
        if credit_total != invoice.credit_total:
            issues.append((invoice.id, ("CREDIT_PROJECTION_MISMATCH",), rows[-1]))
        if refunded_total != invoice.refunded_total:
            issues.append((invoice.id, ("REFUND_PROJECTION_MISMATCH",), rows[-1]))
        if credit_total > invoice.total:
            issues.append((invoice.id, ("CREDIT_EXCEEDS_INVOICE",), rows[-1]))
    for refund in Refund.objects.filter(organisation=organisation).order_by("id"):
        if refund.amount > refund.credit_note.amount:
            issues.append(
                (refund.id, ("REFUND_EXCEEDS_CREDIT_NOTE",), str(refund.amount))
            )
        if refund.status == "APPROVED" and refund.approved_by_id is None:
            issues.append((refund.id, ("REFUND_APPROVAL_MISSING",), str(refund.id)))
    for code, count in suspicious.items():
        if count:
            issues.append(("candidates", (code,), str(count)))
    evidence = {
        "invoices": rows,
        "credit_count": CreditNote.objects.filter(organisation=organisation).count(),
        "refund_count": Refund.objects.filter(organisation=organisation).count(),
        "candidates": suspicious,
    }
    return {
        "source_count": evidence["credit_count"] + evidence["refund_count"],
        "issues": issues,
        "digest": _digest(evidence),
        "evidence": evidence,
    }


def _cutover(organisation):
    return MigrationCutover.objects.get_or_create(
        organisation=organisation, migration_id=MIGRATION_ID
    )[0]


def inventory_mig010(*, organisation):
    assert_transaction_active()
    cutover = _cutover(organisation)
    scan = _scan(organisation)
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
        "migration_id": MIGRATION_ID,
        "phase": cutover.phase,
        "source_count": scan["source_count"],
        "issue_count": len(scan["issues"]),
        "digest": scan["digest"],
    }


def verify_mig010(*, organisation):
    assert_transaction_active()
    cutover = _cutover(organisation)
    scan = _scan(organisation)
    for pk, codes, evidence in scan["issues"]:
        _exception(
            organisation,
            "billing_creditnote" if "CREDIT" in codes[0] else "billing_refund",
            pk,
            codes,
            source_hash=_digest(str(evidence)),
        )
    pending = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=MIGRATION_ID, resolution_state="PENDING"
    ).count()
    previous = cutover.parity_passes if cutover.parity_digest == scan["digest"] else 0
    clean = not scan["issues"] and pending == 0
    cutover.parity_digest = scan["digest"]
    cutover.parity_passes = (previous + 1) if clean else 0
    cutover.stable_full_scan_count = cutover.parity_passes
    cutover.blocker_checks_passed = clean and cutover.parity_passes >= 2
    cutover.last_verified_at = now()
    cutover.phase = "VERIFIED" if clean else "BLOCKED"
    cutover.version += 1
    cutover.save(
        update_fields=[
            "parity_digest",
            "parity_passes",
            "stable_full_scan_count",
            "blocker_checks_passed",
            "last_verified_at",
            "phase",
            "version",
            "updated_at",
        ]
    )
    return {
        "migration_id": MIGRATION_ID,
        "phase": cutover.phase,
        "issue_count": len(scan["issues"]),
        "pending_reconciliations": pending,
        "parity_passes": cutover.parity_passes,
        "blocker_checks_passed": cutover.blocker_checks_passed,
        "digest": scan["digest"],
    }


def constrain_mig010(*, organisation):
    assert_transaction_active()
    cutover = _cutover(organisation)
    if cutover.parity_passes < 2 or not cutover.blocker_checks_passed:
        raise ValueError("MIG-010 requires two stable clean scans before CONSTRAINED.")
    cutover.phase = "CONSTRAINED"
    cutover.version += 1
    cutover.save(update_fields=["phase", "version", "updated_at"])
    return {"migration_id": MIGRATION_ID, "phase": cutover.phase}


def cutover_mig010(*, organisation):
    assert_transaction_active()
    cutover = _cutover(organisation)
    if cutover.phase != "CONSTRAINED":
        raise ValueError("MIG-010 must be CONSTRAINED before cutover.")
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
        "migration_id": MIGRATION_ID,
        "phase": cutover.phase,
        "target_reads_enabled": True,
        "target_writes_enabled": True,
    }


def rollback_mig010(*, organisation, reason):
    assert_transaction_active()
    if not (reason or "").strip():
        raise ValueError("A rollback reason is required.")
    cutover = _cutover(organisation)
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
        "migration_id": MIGRATION_ID,
        "phase": cutover.phase,
        "rollback_at": cutover.rollback_at.isoformat(),
    }
