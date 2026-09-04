from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import OrganisationMembership, Role, User, UserCredential, UserFacilityRole
from accounts.services import ensure_default_permissions
from billing.models import PriceList, ServiceCatalogItem, ServicePrice
from core.clock import local_service_date
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry
from scheduling.services import check_in_patient
from tenancy.models import Department, Facility, FacilityModule, Module, Organisation
from tenancy.services import DEFAULT_MODULES


PASSWORD = "ClinicopusDemo123!"


def ensure_user(username, email, first_name, last_name, password):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "first_name": first_name, "last_name": last_name, "is_active": True},
    )
    changed = []
    for field, value in {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "is_active": True,
    }.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed.append(field)
    if created or not user.check_password(password):
        user.set_password(password)
        changed.append("password")
    if changed:
        user.save(update_fields=sorted(set(changed)))
    return user


class Command(BaseCommand):
    help = "Create synthetic KlinKlik development data; refuses production settings."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is development-only and refuses to run when DJANGO_DEBUG=0.")

        organisation, _ = Organisation.objects.get_or_create(
            slug="clinicopus-demo",
            defaults={"name": "Kampala Medical Centre", "dpo_email": "privacy@clinicopus.local"},
        )
        organisation.name = "Kampala Medical Centre"
        organisation.status = "ACTIVE"
        organisation.dpo_email = "privacy@clinicopus.local"
        organisation.save()

        with tenant_atomic(organisation.id):
            facility, _ = Facility.objects.update_or_create(
                organisation=organisation,
                code="MAIN",
                defaults={"name": "Main Branch", "mode": "CLINIC", "is_active": True},
            )
            departments = {
                code: Department.objects.update_or_create(
                    organisation=organisation,
                    facility=facility,
                    code=code,
                    defaults={"name": name, "is_active": True},
                )[0]
                for code, name in [
                    ("RECEPTION", "Reception"),
                    ("OPD", "Outpatient"),
                    ("TRIAGE", "Triage"),
                    ("BILLING", "Billing"),
                ]
            }
            for code, module_name in DEFAULT_MODULES:
                module, _ = Module.objects.get_or_create(code=code, defaults={"name": module_name})
                FacilityModule.objects.get_or_create(
                    organisation=organisation, facility=facility, module=module
                )

            ensure_default_permissions(organisation)
            roles = {
                code: Role.objects.get(organisation=organisation, template_code=code)
                for code in ["OWNER_ADMIN", "RECEPTION_CASHIER", "NURSE_TRIAGE", "CLINICIAN"]
            }

            users = {}
            for username, first_name, last_name, role_code, department_code in [
                ("admin@clinicopus.local", "Amina", "Administrator", "OWNER_ADMIN", "OPD"),
                ("reception@clinicopus.local", "Ruth", "Reception", "RECEPTION_CASHIER", "RECEPTION"),
                ("nurse@clinicopus.local", "Nabirye", "Nurse", "NURSE_TRIAGE", "TRIAGE"),
                ("doctor@clinicopus.local", "David", "Clinician", "CLINICIAN", "OPD"),
                ("cashier@clinicopus.local", "Grace", "Cashier", "RECEPTION_CASHIER", "BILLING"),
            ]:
                user = ensure_user(username, username, first_name, last_name, PASSWORD)
                users[username] = user
                OrganisationMembership.objects.update_or_create(
                    organisation=organisation, user=user, defaults={"status": "ACTIVE"}
                )
                UserFacilityRole.objects.update_or_create(
                    organisation=organisation,
                    user=user,
                    facility=facility,
                    role=roles[role_code],
                    defaults={
                        "department": departments[department_code],
                        "status": "ACTIVE",
                        "valid_until": None,
                    },
                )

            demo = ensure_user("demo", "demo@example.test", "KlinKlik", "Demo", "ClinicopusDemo!2026")
            users["demo"] = demo
            OrganisationMembership.objects.update_or_create(
                organisation=organisation, user=demo, defaults={"status": "ACTIVE"}
            )
            UserFacilityRole.objects.update_or_create(
                organisation=organisation,
                user=demo,
                facility=facility,
                role=roles["OWNER_ADMIN"],
                defaults={"department": departments["OPD"], "status": "ACTIVE", "valid_until": None},
            )
            UserCredential.objects.update_or_create(
                organisation=organisation,
                user=users["doctor@clinicopus.local"],
                credential_type="Clinical licence",
                defaults={
                    "registration_number": "DEV-DOCTOR-001",
                    "issuing_body": "KlinKlik development fixture",
                    "status": "VALID",
                    "expires_at": None,
                },
            )

            service, _ = ServiceCatalogItem.objects.update_or_create(
                organisation=organisation,
                code="CONSULTATION",
                defaults={"name": "General consultation", "category": "CLINIC", "is_active": True},
            )
            # Referenced catalogue versions are immutable after MIG-001.  Keep
            # the demo seed idempotent without trying to rewrite a version
            # that may already have issued prices or payer bindings.
            price_list, _ = PriceList.objects.get_or_create(
                organisation=organisation,
                stable_code="STANDARD",
                version=1,
                defaults={
                    "name": "Standard cash",
                    "payer_type": "CASH",
                    "active": True,
                    "effective_from": local_service_date(),
                },
            )
            ServicePrice.objects.update_or_create(
                organisation=organisation,
                facility=facility,
                service=service,
                price_list=price_list,
                effective_from=local_service_date(),
                defaults={
                    "amount": "30000.00",
                    "currency": organisation.default_currency,
                    "is_active": True,
                    "active": True,
                    "source_version": "v1",
                },
            )

            patients = {
                patient_no: Patient.objects.update_or_create(
                    organisation=organisation,
                    patient_no=patient_no,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "sex": sex,
                        "phone": phone,
                        "address": "Synthetic development record",
                        "status": "ACTIVE",
                    },
                )[0]
                for patient_no, first_name, last_name, sex, phone in [
                    ("DEMO-0001", "Sarah", "Nakato", "FEMALE", "0700000101"),
                    ("DEMO-0002", "Peter", "Okello", "MALE", "0700000102"),
                    ("DEMO-0003", "Grace", "Namusoke", "FEMALE", "0700000103"),
                ]
            }
            queue_entry = (
                QueueEntry.objects.filter(
                    organisation=organisation,
                    facility=facility,
                    patient=patients["DEMO-0001"],
                    queue_date=local_service_date(),
                    status__in=["WAITING", "CALLED", "IN_TRIAGE", "TRIAGED", "IN_CONSULTATION"],
                )
                .order_by("sequence")
                .first()
            )
            if queue_entry is None:
                queue_entry = check_in_patient(
                    organisation=organisation,
                    facility=facility,
                    actor=users["admin@clinicopus.local"],
                    patient_id=patients["DEMO-0001"].id,
                    department_id=departments["OPD"].id,
                    notes="Synthetic development queue entry",
                )

        self.stdout.write(self.style.SUCCESS("Demo seed ready (development-only)."))
        self.stdout.write(f"organisation_id={organisation.id} slug={organisation.slug} name={organisation.name}")
        self.stdout.write(f"facility_id={facility.id} name={facility.name}")
        self.stdout.write("users=admin@clinicopus.local,reception@clinicopus.local,nurse@clinicopus.local,doctor@clinicopus.local,cashier@clinicopus.local")
        self.stdout.write(f"password={PASSWORD}")
        self.stdout.write("legacy_demo=demo / ClinicopusDemo!2026")
        self.stdout.write("patients=Sarah Nakato, Peter Okello, Grace Namusoke")
        self.stdout.write(f"waiting_queue_id={queue_entry.id}")
