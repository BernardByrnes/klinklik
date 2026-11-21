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
from pharmacy.services import (
    CATEGORIES,
    DISPENSING_UNITS,
    DOSAGE_FORMS,
    create_product,
    set_product_price,
)

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
CATALOGUE_TEMPLATE_VERSION = "1"
CATALOGUE_HEADER = ",".join(sorted(REQUIRED_COLUMNS) + sorted(OPTIONAL_COLUMNS))
MAX_CATALOGUE_BYTES = 512 * 1024
MAX_CATALOGUE_ROWS = 1000

_TRUE_VALUES = {"1", "true", "yes", "y"}
_FALSE_VALUES = {"0", "false", "no", "n"}
_ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
_MAX_DECIMAL = Decimal("1000000000000")


def _decode_content(content):
    if isinstance(content, bytes):
        try:
            raw = content
            return raw, raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CanonicalError(
                "INVALID_FILE_ENCODING", "The catalogue file must be UTF-8.", status_code=400
            ) from exc
    if not isinstance(content, str):
        raise CanonicalError("INVALID_INPUT", "The catalogue file is empty.", status_code=400)
    raw = content.encode("utf-8")
    return raw, content


def _parse_bool(value, field, default, row_errors):
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    row_errors.append(f"{field} has an unsupported boolean value")
    return default


def _parse_money(value, field, row_errors):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidOperation
        if amount <= 0:
            row_errors.append(f"{field} must be positive")
            return None
        if amount != amount.quantize(Decimal("0.01")):
            row_errors.append(f"{field} has too many decimal places")
            return None
        if amount >= _MAX_DECIMAL:
            row_errors.append(f"{field} is too large")
            return None
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        row_errors.append(f"{field} is invalid")
        return None


def _check_length(value, field, limit, row_errors):
    if len(str(value or "")) > limit:
        row_errors.append(f"{field} exceeds {limit} characters")


def validate_catalogue_csv(content, *, template_version=CATALOGUE_TEMPLATE_VERSION):
    if str(template_version) != CATALOGUE_TEMPLATE_VERSION:
        raise CanonicalError(
            "UNSUPPORTED_OPERATION", "Unknown catalogue template version.", status_code=422
        )
    raw, text = _decode_content(content)
    if len(raw) > MAX_CATALOGUE_BYTES:
        raise CanonicalError(
            "INVALID_INPUT",
            "The catalogue file exceeds the byte limit.",
            status_code=400,
            metadata={"max_bytes": MAX_CATALOGUE_BYTES},
        )
    if not text.strip():
        raise CanonicalError("INVALID_INPUT", "The catalogue file is empty.", status_code=400)

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CanonicalError("INVALID_INPUT", "The CSV header is missing.", status_code=400)
    headers = [str(name or "").strip().lstrip("\ufeff").lower() for name in reader.fieldnames]
    duplicates = sorted({name for name in headers if headers.count(name) > 1})
    if duplicates:
        raise CanonicalError(
            "INVALID_INPUT",
            "The CSV header contains duplicate columns.",
            status_code=400,
            metadata={"duplicate_headers": duplicates},
        )
    header_set = set(headers)
    unknown = header_set - _ALLOWED_COLUMNS
    if unknown:
        raise CanonicalError(
            "INVALID_INPUT",
            "The CSV header contains unknown columns.",
            status_code=400,
            metadata={"unknown_columns": sorted(unknown)},
        )
    missing = REQUIRED_COLUMNS - header_set
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
    row_count = 0
    for line_no, raw_row in enumerate(reader, start=2):
        row_count += 1
        if row_count > MAX_CATALOGUE_ROWS:
            raise CanonicalError(
                "INVALID_INPUT",
                "The catalogue file exceeds the row limit.",
                status_code=400,
                metadata={"max_rows": MAX_CATALOGUE_ROWS},
            )
        row_errors = []
        extra_values = raw_row.get(None) or []
        if any(value not in (None, "") for value in extra_values):
            row_errors.append("row has an unexpected number of columns")
        if any(value is None for key, value in raw_row.items() if key is not None):
            row_errors.append("row has an unexpected number of columns")
        row = {
            str(key).strip().lower(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        code = row.get("code", "").upper()
        if not code:
            row_errors.append("code is required")
        elif code in seen_codes:
            row_errors.append("duplicate code in file")
        _check_length(code, "code", 60, row_errors)

        generic_name = row.get("generic_name", "")
        if not generic_name:
            row_errors.append("generic_name is required")
        _check_length(generic_name, "generic_name", 200, row_errors)
        _check_length(row.get("brand_name", ""), "brand_name", 200, row_errors)

        dosage_form = row.get("dosage_form", "").upper()
        if dosage_form not in DOSAGE_FORMS:
            row_errors.append("dosage_form is invalid")
        _check_length(dosage_form, "dosage_form", 30, row_errors)
        dispensing_unit = row.get("dispensing_unit", "").upper()
        if dispensing_unit not in DISPENSING_UNITS:
            row_errors.append("dispensing_unit is invalid")
        _check_length(dispensing_unit, "dispensing_unit", 30, row_errors)
        _check_length(row.get("strength", ""), "strength", 80, row_errors)
        _check_length(row.get("pack_description", ""), "pack_description", 120, row_errors)

        category = row.get("category", "").upper() or "MEDICINE"
        if category not in CATEGORIES:
            row_errors.append("category is invalid")
        _check_length(category, "category", 20, row_errors)

        currency = row.get("currency", "").upper() or "UGX"
        _check_length(currency, "currency", 3, row_errors)
        price = _parse_money(row.get("price", ""), "price", row_errors)
        pack_price = _parse_money(row.get("pack_price", ""), "pack_price", row_errors)
        if pack_price is not None and price is None:
            row_errors.append("pack_price requires price")

        effective_from = None
        if row.get("effective_from"):
            try:
                effective_from = date.fromisoformat(row["effective_from"])
            except ValueError:
                row_errors.append("effective_from is invalid")
        elif price is not None:
            effective_from = date.today()

        prescription_only = _parse_bool(
            row.get("prescription_only", ""), "prescription_only", True, row_errors
        )
        controlled = _parse_bool(row.get("controlled", ""), "controlled", False, row_errors)
        active = _parse_bool(row.get("active", ""), "active", True, row_errors)

        if code:
            seen_codes.add(code)
        normalized = {
            "code": code,
            "generic_name": generic_name,
            "brand_name": row.get("brand_name", ""),
            "dosage_form": dosage_form,
            "strength": row.get("strength", ""),
            "pack_description": row.get("pack_description", ""),
            "dispensing_unit": dispensing_unit,
            "category": category,
            "prescription_only": prescription_only,
            "controlled": controlled,
            "active": active,
            "price": price,
            "currency": currency,
            "effective_from": effective_from,
            "pack_price": pack_price,
        }
        if row_errors:
            errors.append({"line": line_no, "code": code, "errors": row_errors})
        else:
            rows.append({"line": line_no, "data": normalized})
    return rows, errors, hashlib.sha256(raw).hexdigest()


def _existing_codes(*, organisation, facility, codes):
    return sorted(
        MedicationProduct.objects.filter(
            organisation=organisation, facility=facility, code__in=set(codes)
        ).values_list("code", flat=True)
    )


def preview_catalogue_import(*, organisation, facility, content, template_version=CATALOGUE_TEMPLATE_VERSION):
    """Validate a CSV and project scoped counts without writing any record."""
    rows, errors, digest = validate_catalogue_csv(
        content, template_version=str(template_version)
    )
    valid_codes = {row["data"]["code"] for row in rows}
    existing = _existing_codes(
        organisation=organisation, facility=facility, codes=valid_codes
    )
    raw, _text = _decode_content(content)
    return {
        "file_hash": digest,
        "template_version": str(template_version),
        "valid_rows": len(rows),
        "skipped": len(existing),
        "existing_codes": existing[:50],
        "row_errors": errors,
        "byte_count": len(raw),
        "row_count": len(rows) + len(errors),
        "max_bytes": MAX_CATALOGUE_BYTES,
        "max_rows": MAX_CATALOGUE_ROWS,
    }


@transaction.atomic
def import_catalogue(
    *, organisation, facility, actor, content, mode="ALL_OR_NOTHING",
    template_version=CATALOGUE_TEMPLATE_VERSION, file_name="catalogue.csv", file_hash="", request=None,
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
    existing = _existing_codes(
        organisation=organisation, facility=facility, codes=valid_codes
    )
    if existing and mode == "ALL_OR_NOTHING":
        raise CanonicalError(
            "ALREADY_EXISTS",
            "One or more catalogue codes already exist.",
            status_code=409,
            metadata={"existing_codes": existing},
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
