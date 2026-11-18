"""Seed the organisation-wide receipt sequence above existing S-05 numbers.

Receipt identity is unique per organisation. Legacy payments keep their exact
number; the new allocator must resume above any number already issued for the
same local service date instead of restarting at one.
"""

import re

from django.db import migrations


RECEIPT_PATTERN = re.compile(r"^RCT-(\d{8})-(\d{6})$")


def seed_receipt_sequences(apps, schema_editor):
    Payment = apps.get_model("billing", "Payment")
    NumberSequence = apps.get_model("core", "NumberSequence")

    highest = {}
    for organisation_id, receipt_no in Payment.objects.values_list(
        "organisation_id", "receipt_no"
    ).iterator():
        match = RECEIPT_PATTERN.match(receipt_no or "")
        if not match:
            continue
        day, sequence = match.groups()
        key = (organisation_id, day)
        highest[key] = max(highest.get(key, 0), int(sequence))

    for (organisation_id, day), maximum in highest.items():
        period_key = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        sequence, created = NumberSequence.objects.get_or_create(
            organisation_id=organisation_id,
            scope_key="ORG",
            sequence_type="RECEIPT",
            period_key=period_key,
            defaults={"next_value": maximum + 1},
        )
        if not created and sequence.next_value <= maximum:
            sequence.next_value = maximum + 1
            sequence.version += 1
            sequence.save(update_fields=["next_value", "version", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_s05_receipt_number_scope"),
        ("core", "0007_s01_mig001_durable_proof"),
    ]

    operations = [
        migrations.RunPython(seed_receipt_sequences, migrations.RunPython.noop),
    ]
