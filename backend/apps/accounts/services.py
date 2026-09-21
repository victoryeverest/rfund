"""Application services for accounts: registration, login, tokens, OTP.

All business logic lives here (spec §7); GraphQL resolvers stay thin.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import ROLE_PERMISSIONS
from apps.accounts.models import (
    AuthToken,
    LoginAttempt,
    OTPCode,
    Role,
    RolePermission,
    Permission,
    UserRole,
    normalize_phone,
)
from apps.audit.models import AuditAction, record_audit
from apps.core.errors import (
    AuthenticationRequired,
    Conflict,
    PermissionDenied,
    RateLimited,
    RfundError,
    ValidationFailed,
)
from apps.core.middleware import get_request_id

logger = logging.getLogger("rfund.accounts")

User = get_user_model()


# ---------------------------------------------------------------------------
# RBAC bootstrap
# ---------------------------------------------------------------------------
def bootstrap_rbac() -> None:
    """Idempotent creation of roles and permissions (used by migration+seed)."""
    all_codes: set[str] = set()
    for perms in ROLE_PERMISSIONS.values():
        for p in perms:
            all_codes.add(p)
    for code in sorted(all_codes):
        Permission.objects.get_or_create(
            code=code, defaults={"description": code.replace(".", " ")}
        )
    from apps.accounts.constants import ROLE_DESCRIPTIONS

    for role_code, perms in ROLE_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": role_code.replace("_", " ").title(), "description": ROLE_DESCRIPTIONS.get(role_code, "")},
        )
        wanted = set(perms)
        if "*" in wanted:
            wanted = all_codes
            wanted.discard("*")
        current = set(role.permissions.values_list("permission__code", flat=True))
        for code in wanted - current:
            RolePermission.objects.create(
                role=role, permission=Permission.objects.get(code=code)
            )


def grant_role(user, role_code: str, granted_by=None) -> UserRole:
    role = Role.objects.get(code=role_code)
    existing = UserRole.objects.filter(user=user, role=role, revoked_at__isnull=True).first()
    if existing:
        return existing
    ur = UserRole.objects.create(user=user, role=role, granted_by=granted_by)
    record_audit(
        action=AuditAction.ASSIGN,
        resource_type="user_role",
        resource_id=str(user.pk),
        actor=granted_by,
        after={"role": role_code},
        reason="role granted",
    )
    return ur


# ---------------------------------------------------------------------------
# OTP (spec §60, §163)
# ---------------------------------------------------------------------------
def request_otp(
    *, phone: str, purpose: OTPCode.Purpose, ip_address=None, send_sms: bool = True
) -> OTPCode:
    phone = normalize_phone(phone)
    # Rate limit: max 5 OTPs per phone per 15 minutes
    window = timezone.now() - timedelta(minutes=15)
    recent = OTPCode.objects.filter(phone=phone, created_at__gte=window).count()
    if recent >= 5:
        raise RateLimited("Too many verification codes requested. Please wait.")
    code = OTPCode.generate_code()
    otp = OTPCode.objects.create(
        purpose=purpose,
        phone=phone,
        code_hash=OTPCode.hash_code(code),
        expires_at=timezone.now() + settings.OTP_TTL,
        created_by_ip=ip_address,
    )
    if send_sms:
        from integrations.messaging.providers import send_sms_code

        send_sms_code(phone=phone, code=code, purpose=purpose)
    logger.info(
        "otp_requested",
        extra={"event": "otp_requested", "provider": phone, "purpose": purpose},
    )
    return otp


def verify_otp(*, phone: str, purpose: OTPCode.Purpose, code: str) -> bool:
    phone = normalize_phone(phone)
    otp = (
        OTPCode.objects.filter(phone=phone, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise ValidationFailed("No verification code was requested for this phone.")
    if otp.is_consumed:
        raise ValidationFailed("This code has already been used.")
    if otp.is_expired:
        raise ValidationFailed("This code has expired. Please request a new one.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise RateLimited("Too many attempts. Please request a new code.")
    otp.attempts += 1
    if OTPCode.hash_code(code) != otp.code_hash:
        otp.save(update_fields=["attempts"])
        raise ValidationFailed("The code entered is not correct.")
    otp.consumed_at = timezone.now()
    otp.save(update_fields=["attempts", "consumed_at"])
    return True


# ---------------------------------------------------------------------------
# Tokens (spec §60, §176)
# ---------------------------------------------------------------------------
class IssuedTokens:
    """DB records (hash only) + one-time raw values for the API response."""

    __slots__ = ("access", "refresh", "access_raw", "refresh_raw")

    def __init__(self, access, refresh, access_raw, refresh_raw):
        self.access = access
        self.refresh = refresh
        self.access_raw = access_raw
        self.refresh_raw = refresh_raw


def issue_token_pair(
    user, *, device_label: str = "", ip_address=None, refresh_predecessor=None
) -> IssuedTokens:
    access_raw = AuthToken.generate()
    refresh_raw = AuthToken.generate()
    access = AuthToken.objects.create(
        token_hash=AuthToken.hash_token(access_raw),
        user=user,
        kind=AuthToken.Kind.ACCESS,
        expires_at=timezone.now() + settings.ACCESS_TOKEN_TTL,
        device_label=device_label,
        ip_address=ip_address,
    )
    refresh = AuthToken.objects.create(
        token_hash=AuthToken.hash_token(refresh_raw),
        user=user,
        kind=AuthToken.Kind.REFRESH,
        expires_at=timezone.now() + settings.REFRESH_TOKEN_TTL,
        device_label=device_label,
        ip_address=ip_address,
        predecessor=refresh_predecessor,
    )
    return IssuedTokens(access, refresh, access_raw, refresh_raw)


def resolve_token(raw_token: str) -> User:
    """Return the user for a valid access token; raise otherwise."""
    token_hash = AuthToken.hash_token(raw_token)
    token = AuthToken.objects.select_related("user").filter(token_hash=token_hash).first()
    if token is None or not token.is_active:
        raise AuthenticationRequired("Your session has ended. Please sign in again.")
    if token.kind != AuthToken.Kind.ACCESS:
        raise AuthenticationRequired("This token type cannot access the API.")
    if not token.user.is_active:
        raise AuthenticationRequired("This account is not active.")
    return token.user


def refresh_access(raw_refresh: str, *, device_label: str = "", ip_address=None):
    """Rotate refresh token and issue a new pair (spec §60: token rotation)."""
    token_hash = AuthToken.hash_token(raw_refresh)
    refresh = AuthToken.objects.select_related("user").filter(token_hash=token_hash).first()
    if refresh is None or not refresh.is_active:
        raise AuthenticationRequired("Please sign in again.")
    if refresh.kind != AuthToken.Kind.REFRESH:
        raise AuthenticationRequired("This is not a refresh token.")
    # Rotation: revoke old, chain new. Reuse of a revoked token is a signal
    # of theft — revoke the whole chain for that device.
    refresh.revoke()
    issued = issue_token_pair(
        refresh.user,
        device_label=device_label or refresh.device_label,
        ip_address=ip_address,
        refresh_predecessor=refresh,
    )
    return issued


def revoke_user_tokens(user) -> int:
    now = timezone.now()
    count = AuthToken.objects.filter(user=user, revoked_at__isnull=True).exclude(
        expires_at__lt=now
    ).update(revoked_at=now)
    return count


# ---------------------------------------------------------------------------
# Registration & login (spec §60, §131)
# ---------------------------------------------------------------------------
@transaction.atomic
def register_customer(
    *,
    phone: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    email: str | None = None,
    ip_address=None,
    device_id: str = "",
) -> User:
    phone = normalize_phone(phone)
    if User.objects.filter(phone=phone).exists():
        raise Conflict("An account with this phone number already exists.")
    try:
        validate_password(password, User(phone=phone))
    except DjangoValidationError as exc:
        raise ValidationFailed("; ".join(exc.messages)) from exc
    user = User.objects.create_user(
        phone=phone,
        password=password,
        email=email or "",
        first_name=first_name,
        last_name=last_name,
    )
    grant_role(user, "CUSTOMER")
    # Customer financial profile is created lazily via customers.services.
    from apps.notifications.services import emit_event

    emit_event("ACCOUNT_CREATED", {"user_id": str(user.pk), "phone": phone})
    record_audit(
        action=AuditAction.CREATE,
        resource_type="user",
        resource_id=str(user.pk),
        actor=user,
        after={"phone": phone, "roles": ["CUSTOMER"]},
        ip_address=ip_address,
        device_id=device_id,
        request_id=get_request_id(),
    )
    return user


def login(
    *,
    phone: str,
    password: str,
    ip_address=None,
    device_label: str = "",
) -> tuple[User, "IssuedTokens"]:
    phone = normalize_phone(phone)
    if LoginAttempt.recent_failures(phone) >= settings.LOGIN_MAX_FAILURES:
        LoginAttempt.objects.create(phone=phone, ip_address=ip_address, success=False)
        raise RateLimited("Too many failed sign-in attempts. Try again later.")
    user = User.objects.filter(phone=phone).first()
    if user is None or not user.check_password(password):
        LoginAttempt.objects.create(phone=phone, ip_address=ip_address, success=False)
        raise AuthenticationRequired("Phone number or password is not correct.")
    if not user.is_active:
        LoginAttempt.objects.create(phone=phone, ip_address=ip_address, success=False)
        raise AuthenticationRequired("This account is not active.")
    LoginAttempt.objects.create(phone=phone, ip_address=ip_address, success=True)
    issued = issue_token_pair(
        user, device_label=device_label, ip_address=ip_address
    )
    record_audit(
        action=AuditAction.LOGIN,
        resource_type="user",
        resource_id=str(user.pk),
        actor=user,
        ip_address=ip_address,
        request_id=get_request_id(),
    )
    return user, issued


def logout(user, raw_token: str | None = None) -> None:
    if raw_token:
        token = AuthToken.objects.filter(token_hash=AuthToken.hash_token(raw_token)).first()
        if token and token.user_id == user.pk:
            token.revoke()
    revoke_user_tokens(user)
    record_audit(
        action=AuditAction.LOGOUT,
        resource_type="user",
        resource_id=str(user.pk),
        actor=user,
        request_id=get_request_id(),
    )


def require_permission(user, code: str) -> None:
    """Server-side authorization gate (spec §11). Never trust the frontend."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise AuthenticationRequired()
    if not user.has_perm_code(code):
        raise PermissionDenied(f"Missing permission: {code}")


def require_roles(user, *codes: str) -> None:
    if user is None or not getattr(user, "is_authenticated", False):
        raise AuthenticationRequired()
    owned = set(user.role_codes())
    if not owned.intersection(codes):
        raise PermissionDenied()
