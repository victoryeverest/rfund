"""Auth GraphQL types (spec §52, §60): register, OTP, login, refresh, logout."""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.accounts import services as auth
from graphql_api.permissions import current_user, get_context


@strawberry.type
class AuthUser:
    id: strawberry.ID
    phone: str
    email: str
    first_name: str
    last_name: str
    roles: list[str] = strawberry.field(default_factory=list)

    @classmethod
    def from_user(cls, user) -> "AuthUser":
        return cls(
            id=strawberry.ID(str(user.pk)),
            phone=user.phone,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=user.role_codes(),
        )


@strawberry.type
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in_minutes: int
    user: AuthUser


@strawberry.type
class RequestOtpResult:
    sent: bool
    # Populated ONLY in development (settings.DEBUG) so the web UI can show
    # the code without an SMS gateway. Always null in production.
    dev_code: str | None = None


@strawberry.input
class RegisterInput:
    phone: str
    password: str
    first_name: str = ""
    last_name: str = ""


@strawberry.input
class LoginInput:
    phone: str
    password: str
    device_label: str = ""


@strawberry.type
class AuthMutations:
    @strawberry.mutation
    def register_customer(self, info: Info, input: RegisterInput) -> TokenPair:
        ctx = get_context(info)
        user = auth.register_customer(
            phone=input.phone,
            password=input.password,
            first_name=input.first_name,
            last_name=input.last_name,
            ip_address=ctx.ip_address,
            device_id=ctx.device_id,
        )
        issued = auth.issue_token_pair(
            user, device_label="signup", ip_address=ctx.ip_address
        )
        from django.conf import settings

        return TokenPair(
            access_token=issued.access_raw,
            refresh_token=issued.refresh_raw,
            expires_in_minutes=int(settings.ACCESS_TOKEN_TTL.total_seconds() // 60),
            user=AuthUser.from_user(user),
        )

    @strawberry.mutation
    def request_otp(self, info: Info, phone: str, purpose: str = "SIGNUP") -> RequestOtpResult:
        from apps.accounts.models import OTPCode
        from apps.core.errors import ValidationFailed
        from django.conf import settings

        ctx = get_context(info)
        valid = {"SIGNUP", "LOGIN", "PASSWORD_RESET"}
        if purpose not in valid:
            raise ValidationFailed("Unsupported OTP purpose.")
        otp = auth.request_otp(
            phone=phone,
            purpose=OTPCode.Purpose(purpose),
            ip_address=ctx.ip_address,
        )
        dev_code = getattr(otp, "raw_code", None) if settings.DEBUG else None
        return RequestOtpResult(sent=True, dev_code=dev_code)

    @strawberry.mutation
    def verify_otp(self, info: Info, phone: str, code: str, purpose: str = "SIGNUP") -> bool:
        from apps.accounts.models import OTPCode

        return auth.verify_otp(phone=phone, purpose=OTPCode.Purpose(purpose), code=code)

    @strawberry.mutation
    def login_with_otp(self, info: Info, phone: str, code: str, device_label: str = "") -> TokenPair:
        from django.conf import settings

        ctx = get_context(info)
        user, issued = auth.login_with_otp(
            phone=phone,
            code=code,
            ip_address=ctx.ip_address,
            device_label=device_label or "otp-login",
        )
        return TokenPair(
            access_token=issued.access_raw,
            refresh_token=issued.refresh_raw,
            expires_in_minutes=int(settings.ACCESS_TOKEN_TTL.total_seconds() // 60),
            user=AuthUser.from_user(user),
        )

    @strawberry.mutation
    def login(self, info: Info, input: LoginInput) -> TokenPair:
        from django.conf import settings

        ctx = get_context(info)
        user, issued = auth.login(
            phone=input.phone,
            password=input.password,
            ip_address=ctx.ip_address,
            device_label=input.device_label,
        )
        return TokenPair(
            access_token=issued.access_raw,
            refresh_token=issued.refresh_raw,
            expires_in_minutes=int(settings.ACCESS_TOKEN_TTL.total_seconds() // 60),
            user=AuthUser.from_user(user),
        )

    @strawberry.mutation
    def refresh_token(self, info: Info, refresh_token: str) -> TokenPair:
        from django.conf import settings

        ctx = get_context(info)
        issued = auth.refresh_access(
            refresh_token, device_label="web", ip_address=ctx.ip_address
        )
        return TokenPair(
            access_token=issued.access_raw,
            refresh_token=issued.refresh_raw,
            expires_in_minutes=int(settings.ACCESS_TOKEN_TTL.total_seconds() // 60),
            user=AuthUser.from_user(issued.access.user),
        )

    @strawberry.mutation
    def logout(self, info: Info) -> bool:
        user = current_user(info)
        auth.logout(user)
        return True
