from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0002_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="clinicalnote",
            constraint=models.UniqueConstraint(
                fields=("encounter", "note_type"),
                name="uniq_clinical_note_encounter_type",
            ),
        ),
    ]
