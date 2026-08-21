from django.db import transaction
from tenancy.models import Department, Facility, FacilityModule, Module, Organisation


DEFAULT_MODULES = [
    ("PATIENTS", "Patients"),
    ("RECEPTION", "Reception"),
    ("QUEUE", "Queue"),
    ("TRIAGE", "Triage"),
    ("CLINICAL", "Consultation"),
    ("BILLING", "Billing"),
    ("APPOINTMENTS", "Appointments"),
    ("REPORTING", "Reporting"),
]


@transaction.atomic
def create_demo_tenant(name="KlinKlik Demo", slug="clinicopus-demo"):
    organisation, _ = Organisation.objects.get_or_create(
        slug=slug, defaults={"name": name, "dpo_email": "dpo@example.test"}
    )
    facility, _ = Facility.objects.get_or_create(
        organisation=organisation,
        code="MAIN",
        defaults={"name": "Main Facility", "mode": "CLINIC"},
    )
    department, _ = Department.objects.get_or_create(
        organisation=organisation,
        facility=facility,
        code="OPD",
        defaults={"name": "Outpatient Department"},
    )
    for code, module_name in DEFAULT_MODULES:
        module, _ = Module.objects.get_or_create(code=code, defaults={"name": module_name})
        FacilityModule.objects.get_or_create(
            organisation=organisation, facility=facility, module=module
        )
    return organisation, facility, department
