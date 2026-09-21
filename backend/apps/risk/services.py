"""Deterministic risk engine (spec §45).

No ML. Rules produce explainable factors with scores; every decision
lists its factors. Configuration lives in RiskRule rows (auditable,
versioned by version counter), never hard-coded in business logic paths.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from apps.core.money import money
from apps.risk.models import RiskAssessment, RiskFactor, RiskRule

logger = logging.getLogger("rfund.risk")


DEFAULT_RULES = [
    {
        "code": "SAVINGS_CONSISTENCY",
        "name": "Savings consistency",
        "signal": "SAVINGS_CONSISTENCY",
        "weight": 25,
        "parameters": {"min_contributions": 4},
        "description": "Rewards customers with a steady contribution history.",
    },
    {
        "code": "REPAYMENT_HISTORY",
        "name": "Repayment history",
        "signal": "REPAYMENT_HISTORY",
        "weight": 25,
        "parameters": {},
        "description": "Rewards completed loans; penalizes delinquency.",
    },
    {
        "code": "KYC_LEVEL",
        "name": "Identity verification",
        "signal": "KYC_LEVEL",
        "weight": 15,
        "parameters": {},
        "description": "Higher KYC levels reduce risk.",
    },
    {
        "code": "COOPERATIVE_MEMBERSHIP",
        "name": "Cooperative membership",
        "signal": "COOPERATIVE_MEMBERSHIP",
        "weight": 15,
        "parameters": {},
        "description": "Membership of a registered cooperative builds trust.",
    },
    {
        "code": "LOAN_HISTORY",
        "name": "Prior borrowing",
        "signal": "LOAN_HISTORY",
        "weight": 10,
        "parameters": {"max_active": 1},
        "description": "Prior completed loans help; active loans hurt.",
    },
    {
        "code": "TRANSACTION_ACTIVITY",
        "name": "Transaction history",
        "signal": "TRANSACTION_ACTIVITY",
        "weight": 10,
        "parameters": {"min_transactions": 3},
        "description": "General account activity signals engagement.",
    },
]


def ensure_default_rules() -> None:
    for spec in DEFAULT_RULES:
        RiskRule.objects.get_or_create(
            code=spec["code"],
            defaults={k: v for k, v in spec.items() if k != "code"},
        )


def _savings_consistency(customer, params: dict) -> tuple[int, str]:
    from apps.savings.models import SavingsContribution

    count = SavingsContribution.objects.filter(plan__customer=customer).count()
    minimum = int(params.get("min_contributions", 4))
    if count >= minimum * 2:
        return 100, f"{count} contributions recorded"
    if count >= minimum:
        return 60, f"{count} contributions recorded"
    return 10, f"Only {count} contributions recorded"


def _repayment_history(customer, params: dict) -> tuple[int, str]:
    from apps.loans.models import Loan

    loans = list(Loan.objects.filter(customer=customer))
    if not loans:
        return 40, "No borrowing history yet"
    completed = sum(1 for l in loans if l.status == Loan.Status.COMPLETED)
    delinquent = sum(1 for l in loans if l.status in (Loan.Status.DELINQUENT, Loan.Status.DEFAULTED))
    if delinquent:
        return 0, f"{delinquent} delinquent/defaulted loan(s)"
    if completed:
        return 100, f"{completed} loan(s) fully repaid"
    return 50, "Active loan being repaid"


def _kyc_level(customer, params: dict) -> tuple[int, str]:
    from apps.identity.models import KYCProfile

    profile = KYCProfile.objects.filter(customer=customer).first()
    if profile is None or profile.status != KYCProfile.Status.VERIFIED:
        return 0, "Identity not verified"
    scores = {"BASIC": 40, "STANDARD": 75, "ENHANCED": 100}
    return scores.get(profile.level, 40), f"KYC {profile.level}"


def _cooperative_membership(customer, params: dict) -> tuple[int, str]:
    from apps.cooperatives.models import CooperativeMember

    if CooperativeMember.objects.filter(customer=customer, active=True).exists():
        return 100, "Active cooperative member"
    return 20, "Not a cooperative member"


def _loan_history(customer, params: dict) -> tuple[int, str]:
    from apps.loans.models import Loan

    active = Loan.objects.filter(
        customer=customer, status__in=[Loan.Status.ACTIVE, Loan.Status.DELINQUENT]
    ).count()
    max_active = int(params.get("max_active", 1))
    if active > max_active:
        return 0, f"{active} active loans"
    if active == 1:
        return 50, "One active loan"
    return 70, "No active loans"


def _transaction_activity(customer, params: dict) -> tuple[int, str]:
    from apps.payments.models import Payment

    count = Payment.objects.filter(customer=customer, status=Payment.Status.SUCCESS).count()
    minimum = int(params.get("min_transactions", 3))
    if count >= minimum * 3:
        return 100, f"{count} successful payments"
    if count >= minimum:
        return 60, f"{count} successful payments"
    return 20, f"{count} successful payments"


SIGNAL_EVALUATORS = {
    "SAVINGS_CONSISTENCY": _savings_consistency,
    "REPAYMENT_HISTORY": _repayment_history,
    "KYC_LEVEL": _kyc_level,
    "COOPERATIVE_MEMBERSHIP": _cooperative_membership,
    "LOAN_HISTORY": _loan_history,
    "TRANSACTION_ACTIVITY": _transaction_activity,
}


@transaction.atomic
def run_assessment(application) -> RiskAssessment:
    """Explainable, deterministic scoring (§45)."""
    customer = application.customer
    total_weight = Decimal("0")
    weighted_score = Decimal("0")
    factors = []

    for rule in RiskRule.objects.filter(active=True):
        evaluator = SIGNAL_EVALUATORS.get(rule.signal)
        if evaluator is None:
            continue
        score, explanation = evaluator(customer, rule.parameters or {})
        weight = Decimal(str(rule.weight))
        weighted_score += Decimal(score) * weight
        total_weight += weight
        factors.append(
            {
                "rule": rule.code,
                "name": rule.name,
                "score": score,
                "weight": str(weight),
                "explanation": explanation,
            }
        )

    final = money(weighted_score / total_weight) if total_weight else Decimal("0")
    if final >= 65:
        decision = "APPROVE"
    elif final >= 40:
        decision = "REVIEW"
    else:
        decision = "REJECT"

    assessment = RiskAssessment.objects.create(
        application=application,
        score=final,
        decision=decision,
        model_version="rules-v1",
    )
    for f in factors:
        RiskFactor.objects.create(
            assessment=assessment,
            rule_code=f["rule"],
            input_value=f["explanation"],
            score=f["score"],
            weight=f["weight"],
            explanation=f["explanation"],
        )
    logger.info(
        "risk_assessment_completed",
        extra={
            "event": "risk_assessment_completed",
            "reference": application.reference,
            "operation": "run_assessment",
            "status": decision,
        },
    )
    return assessment
