from django.db import migrations, models
import django.db.models.deletion

import core.models
import tenancy.models


POLICY_SQL = """
ALTER TABLE tenancy_facilityworkflowpolicy ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_facilityworkflowpolicy FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS clinicopus_tenant_isolation ON tenancy_facilityworkflowpolicy;
CREATE POLICY clinicopus_tenant_isolation
ON tenancy_facilityworkflowpolicy
USING (organisation_id = current_setting('app.current_org_id')::uuid)
WITH CHECK (organisation_id = current_setting('app.current_org_id')::uuid);
"""


OPTION_CHECK_SQL = """
ALTER TABLE tenancy_facilityworkflowpolicy
    ADD CONSTRAINT workflow_policy_options_are_arrays
    CHECK (
        jsonb_typeof(triage_complaint_options) = 'array'
        AND jsonb_typeof(chronic_condition_options) = 'array'
        AND jsonb_typeof(examination_system_options) = 'array'
        AND jsonb_typeof(counselling_point_options) = 'array'
        AND jsonb_typeof(discount_reason_options) = 'array'
    );
"""


def apply_postgres_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(POLICY_SQL)
        cursor.execute(OPTION_CHECK_SQL)


def reverse_postgres_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE tenancy_facilityworkflowpolicy "
            "DROP CONSTRAINT IF EXISTS workflow_policy_options_are_arrays"
        )
        cursor.execute(
            "DROP POLICY IF EXISTS clinicopus_tenant_isolation "
            "ON tenancy_facilityworkflowpolicy"
        )
        cursor.execute(
            "ALTER TABLE tenancy_facilityworkflowpolicy NO FORCE ROW LEVEL SECURITY"
        )
        cursor.execute(
            "ALTER TABLE tenancy_facilityworkflowpolicy DISABLE ROW LEVEL SECURITY"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
        ("core", "0003_s00_verification_foundation"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FacilityWorkflowPolicy",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.models.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("queue_call_expiry_minutes", models.PositiveIntegerField(default=10)),
                ("queue_no_show_final_attempts", models.PositiveIntegerField(default=3)),
                (
                    "public_board_identity_mode",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PATIENT_NUMBER", "Patient number"),
                            ("FIRST_NAME_INITIAL", "First-name initial"),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                (
                    "triage_complaint_options",
                    models.JSONField(default=tenancy.models.default_option_list),
                ),
                (
                    "chronic_condition_options",
                    models.JSONField(default=tenancy.models.default_option_list),
                ),
                (
                    "examination_system_options",
                    models.JSONField(default=tenancy.models.default_option_list),
                ),
                (
                    "prescription_duration_warning_days",
                    models.PositiveIntegerField(default=90),
                ),
                (
                    "inventory_expiry_warning_horizon_days",
                    models.PositiveIntegerField(default=90),
                ),
                ("blind_stock_count", models.BooleanField(default=True)),
                (
                    "prescription_uncollected_window_days",
                    models.PositiveIntegerField(default=7),
                ),
                (
                    "counselling_point_options",
                    models.JSONField(default=tenancy.models.default_option_list),
                ),
                (
                    "discount_reason_options",
                    models.JSONField(default=tenancy.models.default_option_list),
                ),
                (
                    "discount_approval_threshold",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "cashier_shift_stale_after_minutes",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "cashier_variance_alert_threshold",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("lab_allow_self_verification", models.BooleanField(default=False)),
                ("version", models.PositiveBigIntegerField(default=1)),
                (
                    "facility",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_records",
                        to="tenancy.facility",
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(class)s_records",
                        to="tenancy.organisation",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_workflow_policies",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.UniqueConstraint(
                fields=("facility",),
                name="uniq_workflow_policy_facility",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(queue_call_expiry_minutes__gt=0),
                name="workflow_policy_queue_expiry_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(queue_no_show_final_attempts__gt=0),
                name="workflow_policy_no_show_attempts_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(public_board_identity_mode__isnull=True)
                | models.Q(public_board_identity_mode__in=["PATIENT_NUMBER", "FIRST_NAME_INITIAL"]),
                name="workflow_policy_board_identity_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(prescription_duration_warning_days__gt=0),
                name="workflow_policy_prescription_warning_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(inventory_expiry_warning_horizon_days__gt=0),
                name="workflow_policy_inventory_warning_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(prescription_uncollected_window_days__gt=0),
                name="workflow_policy_uncollected_window_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(discount_approval_threshold__isnull=True)
                | models.Q(discount_approval_threshold__gte=0),
                name="workflow_policy_discount_threshold_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="facilityworkflowpolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(cashier_variance_alert_threshold__isnull=True)
                | models.Q(cashier_variance_alert_threshold__gte=0),
                name="workflow_policy_variance_threshold_nonnegative",
            ),
        ),
        migrations.RunPython(apply_postgres_guards, reverse_postgres_guards),
    ]
