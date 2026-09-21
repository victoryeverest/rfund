"""Test object factories — no external library, no real personal data."""

from __future__ import annotations

from decimal import Decimal

from apps.accounts.services import grant_role
from apps.accounts.models import User
from apps.agents.models import AgentTerritory
from apps.agents.services import register_agent
from apps.customers.services import create_customer_profile
from apps.identity.services import get_or_create_profile, review_kyc, submit_kyc
from apps.ledger.services import ensure_core_accounts
from apps.savings.services import ensure_default_products
from apps.loans.services import ensure_default_products as ensure_loan_products


def make_user(phone: str, password: str = "Passw0rd!23", **kwargs) -> User:
    user = User.objects.create_user(phone=phone, password=password, **kwargs)
    grant_role(user, "CUSTOMER")
    return user


def make_customer(phone: str, *, first_name="Grace", last_name="Bello", **kwargs):
    ensure_core_accounts()
    user = make_user(phone, first_name=first_name, last_name=last_name)
    return create_customer_profile(
        user=user,
        first_name=first_name,
        last_name=last_name,
        state="Kaduna",
        lga="Zaria",
        community="Test Community",
        **kwargs,
    )


def verify_kyc(customer, level: str = "STANDARD"):
    profile = submit_kyc(customer, doc_type="NIN", id_number="11223344556")
    officer = User.objects.filter(roles__role__code="KYC_OFFICER").first()
    if officer is None:
        officer = make_user("+2348000000801")
        grant_role(officer, "KYC_OFFICER")
    return review_kyc(profile, reviewer=officer, decision="APPROVED",
                      reason="test verification", new_level=level)


def make_agent(phone: str, territory_code: str = "TEST-T1"):
    ensure_core_accounts()
    territory, _ = AgentTerritory.objects.get_or_create(
        code=territory_code, defaults={"state": "Kaduna", "lga": "Zaria", "communities": []}
    )
    user = make_user(phone, first_name="Test", last_name="Agent")
    grant_role(user, "AGENT")
    return register_agent(user=user, territory_code=territory_code, business_name="Test Agent")


def make_savings_product():
    ensure_default_products()
    from apps.savings.models import SavingsProduct

    return SavingsProduct.objects.get(code="SAVE_FLEX")


def make_loan_product(code: str = "TRADER"):
    ensure_loan_products()
    from apps.loans.models import LoanProduct

    return LoanProduct.objects.get(code=code)
