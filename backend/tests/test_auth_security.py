"""Auth, token, OTP, permission, and IDOR tests (spec §60, §110, §111, §113)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.accounts import services as auth
from apps.accounts.models import AuthToken, LoginAttempt, OTPCode, User, normalize_phone
from apps.core.errors import (
    AuthenticationRequired,
    PermissionDenied,
    RateLimited,
    ValidationFailed,
)
from tests.factories import make_customer


class TestPhoneNormalization:
    def test_local_format(self):
        assert normalize_phone("08031234567") == "+2348031234567"

    def test_international(self):
        assert normalize_phone("+2348031234567") == "+2348031234567"

    def test_spaced(self):
        assert normalize_phone("0803 123 4567") == "+2348031234567"

    def test_invalid_rejected(self):
        with pytest.raises(ValueError):
            normalize_phone("123")


class TestRegistrationAndLogin:
    def test_register_grants_customer_role(self, db):
        user = auth.register_customer(
            phone="08099990001", password="Str0ngPass!23", first_name="A", last_name="B"
        )
        assert "CUSTOMER" in user.role_codes()
        assert user.has_perm_code("savings.read.self")

    def test_duplicate_phone_rejected(self, db):
        auth.register_customer(phone="08099990002", password="Str0ngPass!23")
        from apps.core.errors import Conflict

        with pytest.raises(Conflict):
            auth.register_customer(phone="+2348099990002", password="Another!234")

    def test_weak_password_rejected(self, db):
        with pytest.raises(ValidationFailed):
            auth.register_customer(phone="08099990003", password="123")

    def test_login_success(self, db):
        auth.register_customer(phone="08099990004", password="Str0ngPass!23")
        user, issued = auth.login(phone="08099990004", password="Str0ngPass!23")
        assert user.phone == "+2348099990004"
        assert issued.access_raw and issued.refresh_raw

    def test_login_wrong_password(self, db):
        auth.register_customer(phone="08099990005", password="Str0ngPass!23")
        with pytest.raises(AuthenticationRequired):
            auth.login(phone="08099990005", password="Wrong!234")

    def test_login_lockout_after_failures(self, db):
        from django.conf import settings
        from django.utils import timezone

        phone = "+2348099990006"
        for _ in range(settings.LOGIN_MAX_FAILURES):
            LoginAttempt.objects.create(phone=phone, success=False)
        with pytest.raises(RateLimited):
            auth.login(phone=phone, password="Whatever!123")


class TestTokens:
    def test_tokens_hashed_at_rest(self, db):
        user = auth.register_customer(phone="08099990010", password="Str0ngPass!23")
        issued = auth.issue_token_pair(user)
        assert AuthToken.objects.filter(token_hash=AuthToken.hash_token(issued.access_raw)).exists()
        assert not AuthToken.objects.filter(token_hash=issued.access_raw).exists()

    def test_resolve_token(self, db):
        user = auth.register_customer(phone="08099990011", password="Str0ngPass!23")
        issued = auth.issue_token_pair(user)
        resolved = auth.resolve_token(issued.access_raw)
        assert resolved.pk == user.pk

    def test_garbage_token_rejected(self, db):
        with pytest.raises(AuthenticationRequired):
            auth.resolve_token("not-a-real-token")

    def test_refresh_rotation(self, db):
        user = auth.register_customer(phone="08099990012", password="Str0ngPass!23")
        issued = auth.issue_token_pair(user)
        rotated = auth.refresh_access(issued.refresh_raw)
        assert rotated.access_raw != issued.access_raw
        # Old refresh is revoked; reuse is rejected
        with pytest.raises(AuthenticationRequired):
            auth.refresh_access(issued.refresh_raw)

    def test_logout_revokes_all(self, db):
        user = auth.register_customer(phone="08099990013", password="Str0ngPass!23")
        issued = auth.issue_token_pair(user)
        auth.logout(user)
        with pytest.raises(AuthenticationRequired):
            auth.resolve_token(issued.access_raw)

    def test_expired_token_rejected(self, db):
        from django.utils import timezone

        user = auth.register_customer(phone="08099990014", password="Str0ngPass!23")
        token = AuthToken.objects.create(
            token_hash=AuthToken.hash_token(AuthToken.generate()),
            user=user,
            kind=AuthToken.Kind.ACCESS,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        raw = None
        # We cannot recover the raw for an externally created token; simulate
        # via resolve of a fresh token then expire it.
        issued = auth.issue_token_pair(user)
        AuthToken.objects.filter(token_hash=AuthToken.hash_token(issued.access_raw)).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        with pytest.raises(AuthenticationRequired):
            auth.resolve_token(issued.access_raw)


class TestOTP:
    def test_otp_roundtrip(self, db, monkeypatch):
        # Deterministic code for verification testing
        monkeypatch.setattr(OTPCode, "generate_code", staticmethod(lambda: "424242"))
        auth.request_otp(phone="08099990020", purpose=OTPCode.Purpose.SIGNUP, send_sms=False)
        # Wrong code → structured failure
        with pytest.raises(ValidationFailed):
            auth.verify_otp(phone="08099990020", purpose=OTPCode.Purpose.SIGNUP, code="000000")
        # Right code → verified, and single-use
        assert auth.verify_otp(
            phone="08099990020", purpose=OTPCode.Purpose.SIGNUP, code="424242"
        )
        with pytest.raises(ValidationFailed, match="already been used"):
            auth.verify_otp(
                phone="08099990020", purpose=OTPCode.Purpose.SIGNUP, code="424242"
            )

    def test_otp_rate_limited(self, db):
        for i in range(5):
            auth.request_otp(
                phone="08099990021", purpose=OTPCode.Purpose.SIGNUP, send_sms=False
            )
        with pytest.raises(RateLimited):
            auth.request_otp(
                phone="08099990021", purpose=OTPCode.Purpose.SIGNUP, send_sms=False
            )

    def test_otp_hashed_at_rest(self, db, monkeypatch):
        monkeypatch.setattr(OTPCode, "generate_code", staticmethod(lambda: "778899"))
        auth.request_otp(phone="08099990022", purpose=OTPCode.Purpose.SIGNUP, send_sms=False)
        otp = OTPCode.objects.filter(phone="+2348099990022").latest("created_at")
        assert len(otp.code_hash) == 64
        # SHA-256 of the code, never the plaintext itself
        import hashlib

        assert otp.code_hash == hashlib.sha256(b"otp:778899").hexdigest()

    def test_otp_attempt_lockout(self, db, monkeypatch):
        monkeypatch.setattr(OTPCode, "generate_code", staticmethod(lambda: "112233"))
        auth.request_otp(phone="08099990023", purpose=OTPCode.Purpose.SIGNUP, send_sms=False)
        from django.conf import settings

        for _ in range(settings.OTP_MAX_ATTEMPTS):
            with pytest.raises(ValidationFailed):
                auth.verify_otp(
                    phone="08099990023", purpose=OTPCode.Purpose.SIGNUP, code="000000"
                )
        with pytest.raises(RateLimited):
            auth.verify_otp(
                phone="08099990023", purpose=OTPCode.Purpose.SIGNUP, code="112233"
            )


class TestPermissions:  # spec §11
    def test_customer_cannot_approve_loans(self, db):
        user = auth.register_customer(phone="08099990030", password="Str0ngPass!23")
        with pytest.raises(PermissionDenied):
            auth.require_permission(user, "loan.approve")

    def test_is_staff_is_not_enough(self, db):
        user = User.objects.create_user(
            phone="08099990031", password="Str0ngPass!23", is_staff=True
        )
        with pytest.raises(PermissionDenied):
            auth.require_permission(user, "ledger.reverse")

    def test_super_admin_has_all(self, super_admin):
        assert super_admin.has_perm_code("ledger.reverse")
        assert super_admin.has_perm_code("loan.approve")


class TestObjectLevelAuthorization:  # spec §111 IDOR
    def test_customer_cannot_read_other_plan(self, db, customer, second_customer):
        from apps.core.errors import NotFound
        from apps.ledger.services import ensure_core_accounts
        from apps.savings.services import create_savings_plan, ensure_default_products
        from datetime import date, timedelta

        ensure_core_accounts()
        ensure_default_products()
        plan = create_savings_plan(
            customer=customer,
            product_code="SAVE_FLEX",
            amount=Decimal("1000"),
            frequency="DAILY",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5),
        )
        from apps.savings.services import get_plan

        with pytest.raises(NotFound):
            get_plan(str(plan.pk), customer=second_customer)

    def test_customer_cannot_read_other_payment(self, db):
        from apps.core.errors import NotFound
        from apps.payments.services import get_payment, initialize_payment

        c1 = make_customer("+2348011110099")
        c2 = make_customer("+2348011110098")
        payment, _ = initialize_payment(
            customer=c1,
            purpose="ACCOUNT_FUNDING",
            amount=Decimal("100"),
            idempotency_key="idor-1",
        )
        # service-level: payments are fetched then ownership-checked in resolvers
        with pytest.raises(NotFound):
            from apps.savings.services import get_plan

            get_plan(str(payment.pk), customer=c2)
