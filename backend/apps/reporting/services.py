"""Reporting services (spec §117).

Read-optimized aggregations with permission checks at the resolver layer.
Numbers come from ledger/domain projections — never hand-counted.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone


def admin_dashboard_snapshot() -> dict:
    """Operational KPIs (spec §71). No PII on overview screens."""
    from apps.agents.models import Agent, AgentTransaction
    from apps.customers.models import Customer
    from apps.fraud.models import FraudAlert
    from apps.ledger.models import LedgerAccount
    from apps.loans.models import Loan, LoanApplication
    from apps.payments.models import Payment
    from apps.savings.models import SavingsPlan

    now = timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    savings_pool = LedgerAccount.objects.filter(code="SAVINGS_POOL").first()
    loan_principal = LedgerAccount.objects.filter(code="LOAN_PRINCIPAL").first()
    interest_income = LedgerAccount.objects.filter(code="INTEREST_INCOME").first()

    active_loans = Loan.objects.filter(status=Loan.Status.ACTIVE)
    return {
        "active_customers": Customer.objects.filter(status=Customer.Status.ACTIVE).count(),
        "new_customers_7d": Customer.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count(),
        "savings_balance": str(savings_pool.balance if savings_pool else 0),
        "active_savings_plans": SavingsPlan.objects.filter(status=SavingsPlan.Status.ACTIVE).count(),
        "loan_portfolio": str(loan_principal.balance if loan_principal else 0),
        "active_loans": active_loans.count(),
        "repayment_volume_30d": str(
            Payment.objects.filter(
                purpose="LOAN_REPAYMENT", status="SUCCESS",
                completed_at__gte=now - timedelta(days=30),
            ).aggregate(t=Sum("amount"))["t"] or 0
        ),
        "interest_income": str(interest_income.balance if interest_income else 0),
        "pending_kyc": _count_pending_kyc(),
        "pending_loan_applications": LoanApplication.objects.filter(
            state__in=["SUBMITTED", "UNDER_REVIEW", "VERIFICATION_REQUIRED"]
        ).count(),
        "payment_failures_24h": Payment.objects.filter(
            status="FAILED", created_at__gte=now - timedelta(hours=24)
        ).count(),
        "reconciliation_exceptions": _count_recon_exceptions(),
        "active_agents": Agent.objects.filter(status=Agent.Status.ACTIVE).count(),
        "agent_collections_today": str(
            AgentTransaction.objects.filter(
                txn_type="CASH_COLLECTION", status="SUCCESS",
                performed_at__gte=day_start,
            ).aggregate(t=Sum("amount"))["t"] or 0
        ),
        "open_fraud_alerts": FraudAlert.objects.filter(
            status__in=["FLAGGED", "UNDER_REVIEW"]
        ).count(),
        "open_support_tickets": _count_open_tickets(),
    }


def _count_pending_kyc() -> int:
    from apps.identity.models import KYCProfile

    return KYCProfile.objects.filter(status__in=["PENDING", "UNDER_REVIEW"]).count()


def _count_recon_exceptions() -> int:
    from apps.settlements.models import ReconciliationItem

    return ReconciliationItem.objects.exclude(status="MATCHED").count()


def _count_open_tickets() -> int:
    from apps.support.models import SupportTicket

    return SupportTicket.objects.filter(status__in=["OPEN", "IN_PROGRESS"]).count()


def customer_growth(days: int = 30) -> list[dict]:
    from apps.customers.models import Customer

    since = timezone.now() - timedelta(days=days)
    rows = (
        Customer.objects.filter(created_at__gte=since)
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return [{"date": str(r["day"]), "new_customers": r["count"]} for r in rows]


def agent_performance() -> list[dict]:
    from apps.agents.models import Agent, AgentTransaction
    from apps.agents.models import AgentSettlement

    out = []
    for agent in Agent.objects.select_related("territory").filter(status=Agent.Status.ACTIVE):
        collections = AgentTransaction.objects.filter(
            agent=agent, txn_type="CASH_COLLECTION", status="SUCCESS"
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        payouts = AgentTransaction.objects.filter(
            agent=agent, txn_type="CUSTOMER_PAYOUT", status="SUCCESS"
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        pending = AgentSettlement.objects.filter(
            agent=agent, status__in=["PENDING_SETTLEMENT", "SETTLEMENT_REQUESTED", "UNDER_REVIEW"]
        ).count()
        out.append(
            {
                "agent_code": agent.agent_code,
                "territory": agent.territory.code,
                "total_collections": str(collections),
                "total_payouts": str(payouts),
                "pending_settlements": pending,
            }
        )
    return out


def loan_portfolio_report() -> dict:
    from apps.loans.models import Loan

    loans = Loan.objects.filter(status__in=["ACTIVE", "DELINQUENT", "DEFAULTED"])
    total_principal = loans.aggregate(t=Sum("outstanding_principal"))["t"] or Decimal("0")
    total_interest = loans.aggregate(t=Sum("outstanding_interest"))["t"] or Decimal("0")
    by_status = {}
    for status, label in Loan.Status.choices:
        by_status[status] = loans.filter(status=status).count()
    return {
        "outstanding_principal": str(total_principal),
        "outstanding_interest": str(total_interest),
        "loans_by_status": by_status,
        "delinquency_rate_pct": str(
            (by_status.get("DELINQUENT", 0) + by_status.get("DEFAULTED", 0))
            / max(loans.count(), 1)
            * 100
        ),
    }


def savings_report() -> dict:
    from apps.ledger.models import LedgerAccount
    from apps.savings.models import SavingsPlan

    pool = LedgerAccount.objects.filter(code="SAVINGS_POOL").first()
    plans = SavingsPlan.objects.all()
    return {
        "total_savings": str(pool.balance if pool else 0),
        "active_plans": plans.filter(status="ACTIVE").count(),
        "completed_plans": plans.filter(status="COMPLETED").count(),
        "total_contributions": str(
            plans.aggregate(t=Sum("total_contributed"))["t"] or 0
        ),
    }


def export_rows(report_type: str) -> list[dict]:
    """CSV-able rows by report type (permission-checked by caller, §118)."""
    if report_type == "agent_performance":
        return agent_performance()
    if report_type == "loan_portfolio":
        return [loan_portfolio_report()]
    if report_type == "savings":
        return [savings_report()]
    if report_type == "customer_growth":
        return customer_growth()
    from apps.core.errors import ValidationFailed

    raise ValidationFailed(f"Unknown report type {report_type!r}")
