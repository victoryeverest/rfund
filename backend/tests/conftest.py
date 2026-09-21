"""Shared pytest fixtures (spec §80)."""

from __future__ import annotations

import pytest

from django.test import RequestFactory


@pytest.fixture(autouse=True)
def _enable_db_access(db):
    """Every test gets DB access."""
    yield


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def staff_user(db):
    from apps.accounts.services import grant_role

    from .factories import make_user

    user = make_user("+2348000000999", password="Staff#2026", is_staff=True)
    grant_role(user, "ADMIN")
    return user


@pytest.fixture
def super_admin(db):
    from apps.accounts.services import grant_role

    from .factories import make_user

    user = make_user("+2348000000900", password="Admin#2026", is_staff=True)
    grant_role(user, "SUPER_ADMIN")
    return user


@pytest.fixture
def customer(db):
    from .factories import make_customer

    return make_customer("+2348011110001", first_name="Test", last_name="Customer")


@pytest.fixture
def verified_customer(db):
    from .factories import make_customer, verify_kyc

    c = make_customer("+2348011110002", first_name="Verified", last_name="Customer")
    verify_kyc(c)
    return c


@pytest.fixture
def second_customer(db):
    from .factories import make_customer

    return make_customer("+2348011110003", first_name="Second", last_name="Customer")


@pytest.fixture
def agent(db):
    from .factories import make_agent

    return make_agent("+2348022220001")


@pytest.fixture
def core_accounts(db):
    from apps.ledger.services import ensure_core_accounts

    ensure_core_accounts()
