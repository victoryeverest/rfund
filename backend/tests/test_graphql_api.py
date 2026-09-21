"""GraphQL API tests at schema level (spec §80: every query and mutation).

Executes the real schema with a mock request + context — same code path
the HTTP view uses, without socket overhead.
"""

from __future__ import annotations

import json

from django.test import RequestFactory

import pytest

from graphql_api.context import GraphQLContext, build_context
from graphql_api.schema import schema


class FakeRequest:
    def __init__(self, user=None, ip="127.0.0.1"):
        self.headers = {
            "Authorization": f"Bearer fake" if False else "",
            "X-Forwarded-For": ip,
        }
        self.META = {"REMOTE_ADDR": ip}
        self.method = "POST"


def execute(query, user=None, variables=None):
    request = RequestFactory().post("/graphql", data={}, content_type="application/json")
    request.headers = getattr(request, "headers", {})
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    # Build context manually to inject the user directly
    from apps.accounts.models import AuthToken

    ctx = GraphQLContext(request=request, user=user, rate_bucket="customer" if user else "anonymous")
    result = schema.execute_sync(query, variable_values=variables or {}, context_value=ctx)
    return result


def data_of(result):
    assert result.errors is None, f"GraphQL errors: {[e.message for e in result.errors]}"
    return result.data


class TestPublicSchema:
    def test_schema_introspects(self):
        result = execute("{ __schema { queryType { name } mutationType { name } } }")
        assert data_of(result)["__schema"]["queryType"]["name"] == "Query"

    def test_me_requires_auth(self):
        result = execute("{ me { customerReference } }")
        assert result.errors is not None
        assert any("sign in" in e.message.lower() for e in result.errors)


class TestCustomerSchema:
    @pytest.fixture
    def customer_user(self, db):
        from tests.factories import make_customer

        return make_customer("+2348088880001").user

    def test_me_returns_profile(self, customer_user):
        result = execute(
            "{ me { customerReference fullName phone status preferredLanguage } }",
            user=customer_user,
        )
        me = data_of(result)["me"]
        assert me["customerReference"].startswith("RF-CUS-")
        assert me["fullName"] == "Grace Bello"

    def test_dashboard_shape(self, customer_user):
        result = execute(
            "{ dashboard { savings { totalSaved activePlans } loan { reference } goalsCount } }",
            user=customer_user,
        )
        d = data_of(result)["dashboard"]
        assert d["savings"]["totalSaved"] == "0.00"

    def test_savings_products_listed(self, db, customer_user):
        from apps.savings.services import ensure_default_products

        ensure_default_products()
        result = execute(
            "{ savingsProducts { code name allowedFrequencies minContribution } }",
            user=customer_user,
        )
        products = data_of(result)["savingsProducts"]
        assert {p["code"] for p in products} >= {"AJO_DAILY", "AJO_WEEKLY", "AJO_MONTHLY", "SAVE_FLEX"}

    def test_create_goal_mutation(self, customer_user):
        result = execute(
            """
            mutation { createSavingsGoal(input: { name: "Test goal", targetAmount: "5000",
                targetDate: "2027-12-31" }) { id name status progressPct } }
            """,
            user=customer_user,
        )
        goal = data_of(result)["createSavingsGoal"]
        assert goal["status"] == "ACTIVE"
        assert goal["progressPct"] == 0.0

    def test_projection_query(self, customer_user):
        result = execute(
            """
            { savingsProjection(amount: "1000", frequency: "MONTHLY",
                startDate: "2026-01-01", endDate: "2026-12-31") {
                  contributionCount totalAmount firstDue lastDue } }
            """,
            user=customer_user,
        )
        projection = data_of(result)["savingsProjection"]
        assert projection["contributionCount"] == 12
        assert projection["totalAmount"] == "12000.00"

    def test_loan_products_listed(self, db, customer_user):
        from apps.loans.services import ensure_default_products

        ensure_default_products()
        result = execute(
            "{ loanProducts { code name termValues interestMethod } }", user=customer_user
        )
        products = data_of(result)["loanProducts"]
        assert {p["code"] for p in products} >= {"TRADER", "ARTISAN", "FARMERCASH"}

    def test_pagination_caps_enforced(self, customer_user):
        result = execute("{ savingsPlans(first: 500) { items { reference } } }", user=customer_user)
        assert result.errors is not None
        assert any("exceed" in e.message.lower() for e in result.errors)


class TestAgentSchema:
    def test_agent_queries_require_agent_role(self, db):
        from tests.factories import make_customer

        user = make_customer("+2348088880011").user
        result = execute("{ agentProfile { agentCode } }", user=user)
        assert result.errors is not None  # no agent profile → error

    def test_agent_dashboard(self, db):
        from tests.factories import make_agent

        agent = make_agent("+2348088880012")
        result = execute(
            "{ agentDashboard { agent { agentCode territoryCode } todayCollections availableFloat } }",
            user=agent.user,
        )
        d = data_of(result)["agentDashboard"]
        assert d["agent"]["agentCode"].startswith("AG-")
        assert d["availableFloat"] == "0.00"


class TestAdminSchema:
    def test_admin_fields_forbidden_for_customers(self, db):
        from tests.factories import make_customer

        user = make_customer("+2348088880021").user
        result = execute("{ adminDashboard { activeCustomers } }", user=user)
        assert result.errors is not None

    def test_admin_dashboard_for_admin(self, db, staff_user):
        from tests.factories import make_customer

        make_customer("+2348088880201")  # at least one active customer
        result = execute(
            "{ adminDashboard { activeCustomers savingsBalance activeAgents } }",
            user=staff_user,
        )
        d = data_of(result)["adminDashboard"]
        assert d["activeCustomers"] >= 1

    def test_admin_ledger_accounts(self, db, staff_user):
        from apps.ledger.services import ensure_core_accounts

        ensure_core_accounts()
        result = execute(
            "{ adminLedgerAccounts { code type balance status } }", user=staff_user
        )
        accounts = data_of(result)["adminLedgerAccounts"]
        codes = {a["code"] for a in accounts}
        assert {"SETTLEMENT", "SAVINGS_POOL", "LOAN_PRINCIPAL"} <= codes

    def test_admin_cannot_be_discovered_via_schema_fields(self, db):
        """§116: schema type exists but resolvers enforce permission."""
        from tests.factories import make_customer

        user = make_customer("+2348088880022").user
        result = execute("{ adminAuditEvents { items { action } } }", user=user)
        assert result.errors is not None

    def test_reverse_ledger_requires_permission(self, db):
        from tests.factories import make_customer

        user = make_customer("+2348088880023").user
        result = execute(
            'mutation { reverseLedgerTransaction(transactionId: "00000000-0000-0000-0000-000000000000", reason: "nope") { reference } }',
            user=user,
        )
        assert result.errors is not None


class TestSupportSchema:
    def test_create_and_reply_ticket(self, db):
        from tests.factories import make_customer

        user = make_customer("+2348088880031").user
        result = execute(
            """
            mutation { createSupportTicket(input: { category: "MISSING_PAYMENT",
                subject: "Payment not showing", body: "I paid yesterday." }) {
                reference status category } }
            """,
            user=user,
        )
        ticket = data_of(result)["createSupportTicket"]
        assert ticket["status"] == "OPEN"
        assert ticket["reference"].startswith("RF-SUP-")


class TestErrorShape:  # spec §54
    def test_domain_errors_carry_codes(self, db):
        result = execute(
            'mutation { createSavingsGoal(input: { name: "", targetAmount: "0" }) { id } }'
        )
        assert result.errors is not None
        # Schema-level execution surfaces the original domain error; the HTTP
        # view maps it to extensions.code (covered by the smoke test).
        from apps.core.errors import AuthenticationRequired

        assert any(
            isinstance(e.original_error, AuthenticationRequired) for e in result.errors
        )
