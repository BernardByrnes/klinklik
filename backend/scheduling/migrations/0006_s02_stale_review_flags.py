from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0005_s02_mig002_canonical_queueentry")]

    operations = [
        migrations.AddField(
            model_name="visit",
            name="stale_review_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="visit",
            name="stale_review_reason",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="visit",
            name="stale_review_required",
            field=models.BooleanField(default=False),
        ),
    ]
