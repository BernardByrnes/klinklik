"""PHM-007 catalogue import mechanics with row-level validation."""

import csv
import hashlib
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from audit.services import record_event
from core.errors import CanonicalError
from core.services import assert_transaction_active
from pharmacy.models import MedicationProduct
from pharmacy.services import create_product, set_product_price

REQUIRED_COLUMNS = {
    "code",
    "generic_name",
    "dosage_form",
    "dispensing_unit",
    "category",
}
OPTIONAL_COLUMNS = {
    "brand_name",
    "strength",
    "pack_description",
    "prescription_only",
    "controlled",
    "active",
    "price",
    "currency",
    "effective_from",
    "pack_price",
}


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def validate_catalogue_csv(content, *, template_version="1"):
    if template_version != "1":
        raise CanonicalError("UNSUPPORTED_OPERATION", "Unknown catalogue template version.", status_code=422)
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CanonicalError(
                "INVALID_FILE_ENCODING", "The catalogue file must be UTF-8.", status_code=400
            ) from exc
    if not isinstance(content, str) or not content.strip():
        raise CanonicalError("INVALID_INPUT", "The catalogue file is empty.", status_code=400)
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise CanonicalError("INVALID_INPUT", "The CSV header is missing.", status_code=400)
    headers = {str(name).strip().lower() for name in reader.fieldnames if name}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CanonicalError(
            "INVALID_INPUT",
            "The CSV template is missing required columns.",
            status_code=400,
            metadata={"missing_columns": sorted(missing)},
        )
    rows = []
    errors = []
    seen_codes = set()
    for line_no, raw in enumerate(reader, start=2):
        row = {str(key).strip().lower(): (value or "").strip() for key, value in raw.items() if key}
        code = row.get("code", "").upper()
        row_errors = []
        if not code:
            row_errors.append("code is required")
        elif code in seen_codes:
            row_errors.append("duplicate code in file")
        if not row.get("generic_name"):
            row_errors.append("generic_name is required")
        if not row.get("dosage_form"):
            row_errors.append("dosage_form is required")
        if not row.get("dispensing_unit"):
            row_errors.append("dispensing_unit is required")
        if row.get("category", "MEDICINE").upper() not in {"MEDICINE", "CONSUMABLE", "SUNDRY"}:
            row_errors.append("category is invalid")
        price = None
        if row.get("price"):
            try:
                price = Decimal(row["price"]).quantize(Decimal("0.01"))
                if price <= 0:
                    row_errors.append("price must be positive")
            except (InvalidOperation, ValueError):
                row_errors.append("price is invalid")
        effective_from = None
        if row.get("effective_from"):
            try:
                effective_from = date.fromisoformat(row["effective_from"])
            except ValueError:
                row_errors.append("effective_from is invalid")
        elif price is not None:
            effective_from = date.today()
        if code:
            seen_codes.add(code)
        normalized = {
            "code": code,
            "generic_name": row.get("generic_name", ""),
            "brand_name": row.get("brand_name", ""),
            "dosage_form": row.get("dosage_form", "").upper(),
            "strength": row.get("strength", ""),
            "pack_description": row.get("pack_description", ""),
            "dispensing_unit": row.get("dispensing_unit", "").upper(),
            "category": row.get("category", "MEDICINE").upper() or "MEDICINE",
            "prescription_only": _truthy(row.get("prescription_only", "true")),
            "controlled": _truthy(row.get("controlled")),
            "active": _truthy(row.get("active", "true")),
            "price": price,
            "currency": row.get("currency", "UGX").upper() or "UGX",
            "effective_from": effective_from,
            "pack_price": row.get("pack_price") or None,
        }
        if row_errors:
            errors.append({"line": line_no, "code": code, "errors": row_errors})
        else:
            rows.append({"line": line_no, "data": normalized})
    return rows, errors, hashlib.sha256(content.encode("utf-8")).hexdigest()


@transaction.atomic
def import_catalogue(
    *, organisation, facility, actor, content, mode="ALL_OR_NOTHING",
    template_version="1", file_name="catalogue.csv", file_hash="", request=None,
):
    assert_transaction_active()
    mode = str(mode or "ALL_OR_NOTHING").upper()
    if mode not in {"ALL_OR_NOTHING", "VALID_ROWS_ONLY"}:
        raise CanonicalError("INVALID_INPUT", "Select a valid import mode.", status_code=400)
    rows, errors, digest = validate_catalogue_csv(
        content, template_version=str(template_version)
    )
    if file_hash and str(file_hash).lower() != digest:
        raise CanonicalError("INVALID_INPUT", "The file hash does not match.", status_code=400)
    if errors and mode == "ALL_OR_NOTHING":
        raise CanonicalError(
            "INVALID_INPUT",
            "The catalogue has row errors; nothing was imported.",
            status_code=400,
            metadata={"row_errors": errors},
        )
    valid_codes = {row["data"]["code"] for row in rows}
    existing = set(
        MedicationProduct.objects.filter(
            organisation=organisation, facility=facility, code__in=valid_codes
        ).values_list("code", flat=True)
    )
    if existing and mode == "ALL_OR_NOTHING":
        raise CanonicalError(
            "ALREADY_EXISTS",
            "One or more catalogue codes already exist.",
            status_code=409,
            metadata={"existing_codes": sorted(existing)},
        )
    imported = 0
    skipped = len(existing)
    for row in rows:
        values = dict(row["data"])
        if values["code"] in existing:
            continue
        price = values.pop("price")
        currency = values.pop("currency")
        effective_from = values.pop("effective_from")
        pack_price = values.pop("pack_price")
        product = create_product(
            organisation=organisation,
            facility=facility,
            actor=actor,
            payload=values,
            confirm_duplicate=True,
        )
        if price is not None:
            set_product_price(
                organisation=organisation,
                facility=facility,
                actor=actor,
                product_id=product.id,
                amount=price,
                currency=currency,
                effective_from=effective_from,
                pack_price=pack_price,
                source_event_id=f"IMPORT:{digest[:16]}:{product.code}",
            )
        imported += 1
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="CatalogueImport",
        entity_id=digest[:32],
        after={
            "file_name": str(file_name)[:120],
            "file_hash": digest,
            "mode": mode,
            "imported": imported,
            "skipped": skipped,
            "errors": len(errors),
        },
        event_code="CATALOGUE_IMPORTED",
    )
    return {
        "file_hash": digest,
        "mode": mode,
        "imported": imported,
        "skipped": skipped,
        "error_count": len(errors),
        "row_errors": errors,
    }
