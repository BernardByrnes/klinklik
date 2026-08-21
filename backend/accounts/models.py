import uuid
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from core.models import FacilityScopedModel, OrganisationScopedModel, UUIDModel


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("username is required")
        user = self.model(username=username.lower().strip(), **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    pin_hash = models.CharField(max_length=128, blank=True)

    objects = UserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.get_full_name() or self.username

    def get_full_name(self):
        return " ".join(value for value in [self.first_name, self.last_name] if value).strip()

    def has_capability(self, code, facility=None):
        if self.is_superuser:
            return True
        organisation = getattr(self, "_request_organisation", None)
        if organisation is None:
            return False
        grants = UserFacilityRole.objects.filter(
            organisation=organisation, user=self, status="ACTIVE"
        ).select_related("role")
        if facility is not None:
            grants = grants.filter(models.Q(facility=facility) | models.Q(facility__isnull=True))
        return RolePermission.objects.filter(
            organisation=organisation,
            role__in=[grant.role_id for grant in grants],
            permission__code=code,
        ).exists()


class OrganisationMembership(OrganisationScopedModel):
    STATUS_CHOICES = [("ACTIVE", "Active"), ("REVOKED", "Revoked")]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "user"], name="uniq_membership_organisation_user"
            )
        ]


class Permission(UUIDModel):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    sensitivity_tier = models.CharField(max_length=2, default="T1")


class Role(OrganisationScopedModel):
    name = models.CharField(max_length=120)
    template_code = models.CharField(max_length=80, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "name"], name="uniq_role_org_name")
        ]


class RolePermission(OrganisationScopedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="role_permissions")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uniq_role_permission")
        ]


class UserFacilityRole(OrganisationScopedModel):
    STATUS_CHOICES = [("ACTIVE", "Active"), ("EXPIRED", "Expired"), ("REVOKED", "Revoked")]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="facility_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_grants")
    facility = models.ForeignKey(
        "tenancy.Facility", on_delete=models.PROTECT, null=True, blank=True, related_name="user_grants"
    )
    department = models.ForeignKey(
        "tenancy.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_grants",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    valid_until = models.DateTimeField(null=True, blank=True)


class UserCredential(OrganisationScopedModel):
    STATUS_CHOICES = [
        ("VALID", "Valid"),
        ("EXPIRED", "Expired"),
        ("UNVERIFIED", "Unverified"),
    ]

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="credentials")
    credential_type = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=120)
    issuing_body = models.CharField(max_length=150, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="UNVERIFIED")


class AuthSession(OrganisationScopedModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="auth_sessions")
    access_token_hash = models.CharField(max_length=64, unique=True)
    refresh_token_hash = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    rotated_from = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="rotated_children"
    )
    last_seen_at = models.DateTimeField(auto_now=True)

    @property
    def is_active_session(self):
        from django.utils import timezone

        return self.revoked_at is None and self.refresh_expires_at > timezone.now()
