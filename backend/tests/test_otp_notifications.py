"""Tests for OTP login (§60), customer notifications feed (§47/§48/§107),
and dev-only OTP code exposure."""

from __future__ import annotations

import pytest

from apps.accounts import services as auth
from apps.accounts.models import OTPCode
from apps.core.errors import AuthenticationRequired, ValidationFailed
from graphql_api.context import GraphQLContext
from graphql_api.schema import schema
from tests.factories import make_customer
from tests.test_graphql_api import data_of


def execute(query, user=None, variables=None):
    from django.test import RequestFactory

    request = RequestFactory().post("/graphql", data={}, content_type="application/json")
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    ctx = GraphQLContext(request=request, user=user, rate_bucket="customer" if user else "anonymous")
    return schema.execute_sync(query, variable_values=variables or {}, context_value=ctx)


class TestOtpLoginService:
    def test_login_with_otp_issues_tokens(self, db):
        auth.register_customer(phone="08077770001", password="Str0ngPass!23")
        otp = auth.request_otp(
            phone="08077770001", purpose=OTPCode.Purpose.LOGIN, send_sms=False
        )
        code = getattr(otp, "raw_code", None)
        assert code, "request_otp must attach raw_code for dev visibility"
        user, issued = auth.login_with_otp(phone="08077770001", code=code)
        assert user.phone == "+2348077770001"
        assert issued.access_raw and issued.refresh_raw

    def test_login_with_otp_consumes_code(self, db):
        auth.register_customer(phone="08077770002", password="Str0ngPass!23")
        otp = auth.request_otp(phone="08077770002", purpose=OTPCode.Purpose.LOGIN, send_sms=False)
        code = otp.raw_code
        auth.login_with_otp(phone="08077770002", code=code)
        # Reuse must fail — one-time codes.
        with pytest.raises(ValidationFailed):
            auth.login_with_otp(phone="08077770002", code=code)

    def test_login_with_otp_wrong_code(self, db):
        auth.register_customer(phone="08077770003", password="Str0ngPass!23")
        auth.request_otp(phone="08077770003", purpose=OTPCode.Purpose.LOGIN, send_sms=False)
        with pytest.raises(ValidationFailed):
            auth.login_with_otp(phone="08077770003", code="000000")

    def test_login_with_otp_unknown_phone(self, db):
        otp = auth.request_otp(phone="08077770004", purpose=OTPCode.Purpose.LOGIN, send_sms=False)
        with pytest.raises(AuthenticationRequired):
            auth.login_with_otp(phone="08077770004", code=otp.raw_code)

    def test_signup_purpose_cannot_login(self, db):
        """A SIGNUP-purpose code must not grant a LOGIN session."""
        auth.register_customer(phone="08077770005", password="Str0ngPass!23")
        otp = auth.request_otp(phone="08077770005", purpose=OTPCode.Purpose.SIGNUP, send_sms=False)
        with pytest.raises(ValidationFailed):
            auth.login_with_otp(phone="08077770005", code=otp.raw_code)


class TestOtpLoginGraphQL:
    def test_request_and_login_flow(self, db):
        from django.test import override_settings

        auth.register_customer(phone="08066660001", password="Str0ngPass!23")

        with override_settings(DEBUG=True):
            result = execute(
                'mutation($phone: String!) { requestOtp(phone: $phone, purpose: "LOGIN") { sent devCode } }',
                variables={"phone": "08066660001"},
            )
            payload = data_of(result)["requestOtp"]
            assert payload["sent"] is True
            assert payload["devCode"], "with DEBUG=True the dev code must be exposed for the web UI"

            result = execute(
                "mutation($phone: String!, $code: String!) { loginWithOtp(phone: $phone, code: $code)"
                " { accessToken refreshToken user { phone } } }",
                variables={"phone": "08066660001", "code": payload["devCode"]},
            )
            pair = data_of(result)["loginWithOtp"]
            assert pair["accessToken"] and pair["refreshToken"]
            assert pair["user"]["phone"] == "+2348066660001"

    def test_devcode_never_leaks_when_debug_off(self, db):
        """Security property: non-DEBUG environments must never see the raw code."""
        from django.conf import settings

        if settings.DEBUG:
            import pytest

            pytest.skip("this suite runs with DEBUG=False; nothing to assert")
        auth.register_customer(phone="08066660003", password="Str0ngPass!23")
        result = execute(
            'mutation { requestOtp(phone: "08066660003", purpose: "LOGIN") { sent devCode } }'
        )
        payload = data_of(result)["requestOtp"]
        assert payload["sent"] is True
        assert payload["devCode"] is None

    def test_login_with_otp_bad_code_is_error(self, db):
        auth.register_customer(phone="08066660002", password="Str0ngPass!23")
        result = execute(
            'mutation { requestOtp(phone: "08066660002", purpose: "LOGIN") { sent devCode } }'
        )
        assert data_of(result)["requestOtp"]["sent"] is True
        result = execute(
            'mutation { loginWithOtp(phone: "08066660002", code: "999999") { accessToken } }'
        )
        assert result.errors is not None


class TestNotificationsFeed:
    def test_notifications_requires_auth(self, db):
        result = execute("{ notifications { items { id eventCode label } totalCount } }")
        assert result.errors is not None

    def test_notifications_scoped_to_customer(self, db):
        from apps.notifications.services import emit_event

        mine = make_customer("+2348055550001")
        other = make_customer("+2348055550002")
        emit_event(
            "SAVINGS_CREATED",
            {"customer_id": str(mine.pk), "plan_reference": "RF-SAV-X", "amount": "1000.00"},
        )
        emit_event(
            "SAVINGS_PAYMENT_RECEIVED",
            {"customer_id": str(mine.pk), "reference": "RF-PAY-Y", "amount": "500.00"},
        )
        emit_event(
            "SAVINGS_CREATED",
            {"customer_id": str(other.pk), "plan_reference": "RF-SAV-Z", "amount": "900.00"},
        )

        result = execute(
            "{ notifications { items { eventCode label amount reference dispatched } totalCount } }",
            user=mine.user,
        )
        feed = data_of(result)["notifications"]
        assert feed["totalCount"] == 2
        codes = [i["eventCode"] for i in feed["items"]]
        assert codes.count("SAVINGS_CREATED") == 1
        assert codes.count("SAVINGS_PAYMENT_RECEIVED") == 1
        by_code = {i["eventCode"]: i for i in feed["items"]}
        assert by_code["SAVINGS_CREATED"]["reference"] == "RF-SAV-X"
        assert by_code["SAVINGS_PAYMENT_RECEIVED"]["amount"] == "500.00"
        assert by_code["SAVINGS_CREATED"]["label"] == "Savings plan created"

    def test_empty_feed(self, db):
        customer = make_customer("+2348055550003")
        result = execute("{ notifications { items { id } totalCount } }", user=customer.user)
        feed = data_of(result)["notifications"]
        assert feed["totalCount"] == 0
        assert feed["items"] == []
