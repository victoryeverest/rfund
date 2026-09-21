"""Accounts: authentication identity, roles, granular permissions, tokens, OTP.

Separate from financial profiles (spec §10): User = who you are;
Customer/Agent/StaffProfile = what you do. A user may hold several roles.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel


def uuid4_default():
    return uuid.uuid4()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, *, phone, password=None, email=None, **extra):
        if not phone:
            raise ValueError("phone is required")
        user = self.model(phone=self.normalize_phone(phone), email=email or "", **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_superuser(self, *, phone, password, email=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone=phone, password=password, email=email, **extra)

    @staticmethod
    def normalize_phone(phone: str) -> str:
        return normalize_phone(phone)


def normalize_phone(phone: str) -> str:
    """Normalize Nigerian numbers to E.164-ish +234XXXXXXXXXX."""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("234") and len(digits) == 13:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"+234{digits[1:]}"
    if len(digits) == 10:
        return f"+234{digits}"
    raise ValueError(f"Unsupported phone format: {phone!r}")


class User(AbstractBaseUser, PermissionsMixin):
    """Authentication identity (spec §10, §60). Phone-first for rural users."""

    id = models.UUIDField(primary_key=True, default=uuid4_default, editable=False)
    phone = models.CharField(max_length=16, unique=True, db_index=True)
    email = models.EmailField(blank=True, default="", db_index=True)
    first_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    status = models.CharField(max_length=12, default="ACTIVE")
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["email"])]

    def __str__(self) -> str:
        name = (self.first_name + " " + self.last_name).strip()
        return f"{name} ({self.phone})" if name else self.phone

    # -- RBAC ---------------------------------------------------------------
    def role_codes(self) -> list[str]:
        return list(self.roles.values_list("role__code", flat=True))

    def permission_codes(self) -> set[str]:
        perms = set()
        for ur in self.roles.select_related("role").prefetch_related(
            "role__permissions__permission"
        ):
            perms.update(
                p.permission.code
                for p in ur.role.permissions.select_related("permission")
            )
        # Django superuser bypass is NOT used for financial permissions
        # (spec §11). Only explicit grants count.
        return perms

    def has_perm_code(self, code: str) -> bool:
        return code in self.permission_codes()



class Role(models.Model):
    """Roles (spec §11). Permissions attach to roles, never to is_staff."""

    code = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.code


class Permission(models.Model):
    code = models.CharField(max_length=60, primary_key=True)
    description = models.CharField(max_length=200, blank=True, default="")

    def __str__(self) -> str:
        return self.code


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="roles"
    )

    class Meta:
        unique_together = [("role", "permission")]


class UserRole(UUIDModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="roles", db_index=True
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    granted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_user_role",
            )
        ]


class AuthToken(UUIDModel):
    """Opaque, hashed-at-rest tokens with rotation + revocation (spec §60).

    kind=ACCESS short-lived; kind=REFRESH long-lived and rotated on use.
    Rotation chain stored via `predecessor` for reuse detection.
    """

    class Kind(models.TextChoices):
        ACCESS = "ACCESS", "Access"
        REFRESH = "REFRESH", "Refresh"

    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="auth_tokens", db_index=True
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    device_label = models.CharField(max_length=120, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    predecessor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="successors"
    )

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_expired and self.revoked_at is None

    @staticmethod
    def generate() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(raw: str) -> str:
        import hashlib

        return hashlib.sha256(raw.encode()).hexdigest()

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            AuthToken.objects.filter(pk=self.pk).update(revoked_at=self.revoked_at)


class OTPCode(UUIDModel):
    """OTP architecture (spec §60, §163): hashed, expiring, attempt-capped."""

    class Purpose(models.TextChoices):
        SIGNUP = "SIGNUP", "Signup verification"
        LOGIN = "LOGIN", "Login verification"
        STEP_UP = "STEP_UP", "Step-up authentication"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
        PHONE_CHANGE = "PHONE_CHANGE", "Phone change"

    purpose = models.CharField(max_length=20, choices=Purpose.choices, db_index=True)
    phone = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "purpose", "-created_at"])]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @staticmethod
    def generate_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def hash_code(code: str) -> str:
        import hashlib

        return hashlib.sha256(f"otp:{code}".encode()).hexdigest()


class LoginAttempt(models.Model):
    """Throttling evidence for login / OTP endpoints (spec §113)."""

    phone = models.CharField(max_length=16, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "-created_at"])]

    @staticmethod
    def recent_failures(phone: str, window: timedelta | None = None) -> int:
        window = window or timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        since = timezone.now() - window
        return LoginAttempt.objects.filter(
            phone=phone, success=False, created_at__gte=since
        ).count()
