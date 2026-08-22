from django.db import migrations, models


def migrate_legacy_complaints(apps, schema_editor):
    Encounter = apps.get_model("clinical", "Encounter")
    ClinicalNote = apps.get_model("clinical", "ClinicalNote")

    for encounter in Encounter.objects.all().iterator():
        if encounter.complaints:
            continue
        note = ClinicalNote.objects.filter(
            encounter_id=encounter.pk,
            note_type="CONSULTATION",
        ).only("content").first()
        content = note.content if note is not None else {}
        legacy = content.get("presenting_complaint") if isinstance(content, dict) else None
        if not isinstance(legacy, str) or not legacy.strip():
            continue
        encounter.complaints = [{
            "text": legacy,
            "duration_value": None,
            "duration_unit": None,
        }]
        encounter.save(update_fields=["complaints"])


def clear_complaints(apps, schema_editor):
    Encounter = apps.get_model("clinical", "Encounter")
    Encounter.objects.all().update(complaints=[])


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0003_clinicalnote_unique_encounter_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="encounter",
            name="complaints",
            field=models.JSONField(default=list),
        ),
        migrations.RunPython(migrate_legacy_complaints, clear_complaints),
    ]
