"""Customer-facing GraphQL types: me, profile, KYC, dashboard."""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.customers import services as customer_services
from apps.identity import services as kyc_services
from apps.ledger import services as ledger_services
from apps.loans.models import Loan, LoanApplication, RepaymentScheduleItem
from apps.savings.models import SavingsPlan, SavingsScheduleItem
from graphql_api.permissions import current_customer, current_user, get_context
from graphql_api.types_auth import AuthUser
from graphql_api.types_common import page_info


@strawberry.type
class CustomerType:
    id: strawberry.ID
    customer_reference: str
    first_name: str
    middle_name: str
    last_name: str
    full_name: str
    phone: str
    email: str
    date_of_birth: str | None
    gender: str
    occupation: str
    address: str
    state: str
    lga: str
    community: str
    preferred_language: str
    status: str
    kyc_tier: str

    @classmethod
    def from_model(cls, c) -> "CustomerType":
        return cls(
            id=strawberry.ID(str(c.pk)),
            customer_reference=c.customer_reference,
            first_name=c.first_name,
            middle_name=c.middle_name,
            last_name=c.last_name,
            full_name=c.full_name,
            phone=c.phone,
            email=c.email,
            date_of_birth=str(c.date_of_birth) if c.date_of_birth else None,
            gender=c.gender,
            occupation=c.occupation,
            address=c.address,
            state=c.state,
            lga=c.lga,
            community=c.community,
            preferred_language=c.preferred_language,
            status=c.status,
            kyc_tier=c.kyc_tier,
        )


@strawberry.type
class KYCStatusType:
    status: str
    level: str
    verified_at: str | None
    failure_reason: str


@strawberry.type
class DashboardSavings:
    total_saved: str
    active_plans: int
    next_contribution_date: str | None
    next_contribution_amount: str | None


@strawberry.type
class DashboardLoan:
    loan_id: strawberry.ID
    reference: str
    outstanding: str
    next_repayment_date: str | None
    next_repayment_amount: str | None
    status: str


@strawberry.type
class Dashboard:
    savings: DashboardSavings
    loan: DashboardLoan | None
    goals_count: int
    unread_notifications: int


@strawberry.type
class MeQueries:
    @strawberry.field
    def me(self, info: Info) -> CustomerType:
        customer = current_customer(info)
        return CustomerType.from_model(customer)

    @strawberry.field
    def kyc_status(self, info: Info) -> KYCStatusType:
        customer = current_customer(info)
        profile = kyc_services.get_or_create_profile(customer)
        return KYCStatusType(
            status=profile.status,
            level=profile.level,
            verified_at=str(profile.verified_at) if profile.verified_at else None,
            failure_reason=profile.failure_reason,
        )

    @strawberry.field
    def dashboard(self, info: Info) -> Dashboard:
        customer = current_customer(info)
        total_saved = ledger_services.customer_savings_balance(customer)
        active_plans = SavingsPlan.objects.filter(
            customer=customer, status=SavingsPlan.Status.ACTIVE
        )
        next_item = (
            SavingsScheduleItem.objects.filter(
                plan__customer=customer,
                status__in=[SavingsScheduleItem.Status.UPCOMING, SavingsScheduleItem.Status.DUE],
            )
            .order_by("due_date")
            .first()
        )
        savings = DashboardSavings(
            total_saved=str(total_saved),
            active_plans=active_plans.count(),
            next_contribution_date=str(next_item.due_date) if next_item else None,
            next_contribution_amount=str(next_item.amount) if next_item else None,
        )
        loan = Loan.objects.filter(
            customer=customer, status__in=[Loan.Status.ACTIVE, Loan.Status.DELINQUENT]
        ).first()
        loan_info = None
        if loan:
            next_repay = loan.repayment_schedule.filter(
                status__in=[
                    RepaymentScheduleItem.Status.UPCOMING,
                    RepaymentScheduleItem.Status.DUE,
                    RepaymentScheduleItem.Status.PARTIALLY_PAID,
                ]
            ).order_by("sequence").first()
            loan_info = DashboardLoan(
                loan_id=strawberry.ID(str(loan.pk)),
                reference=loan.reference,
                outstanding=str(loan.total_outstanding),
                next_repayment_date=str(next_repay.due_date) if next_repay else None,
                next_repayment_amount=str(next_repay.total_due - next_repay.amount_paid) if next_repay else None,
                status=loan.status,
            )
        from apps.notifications.models import NotificationDelivery
        from apps.savings.models import SavingsGoal

        return Dashboard(
            savings=savings,
            loan=loan_info,
            goals_count=SavingsGoal.objects.filter(
                customer=customer, status=SavingsGoal.Status.ACTIVE
            ).count(),
            unread_notifications=NotificationDelivery.objects.filter(
                event__payload__customer_id=str(customer.pk)
            ).count(),
        )


@strawberry.input
class UpdateProfileInput:
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    email: str | None = None
    date_of_birth: str | None = None  # YYYY-MM-DD
    gender: str | None = None
    occupation: str | None = None
    address: str | None = None
    state: str | None = None
    lga: str | None = None
    community: str | None = None
    preferred_language: str | None = None


@strawberry.input
class SubmitKYCInput:
    doc_type: str
    id_number: str
    storage_key: str = ""


@strawberry.type
class ProfileMutations:
    @strawberry.mutation
    def update_profile(self, info: Info, input: UpdateProfileInput) -> CustomerType:
        customer = current_customer(info)
        fields = {}
        for key in (
            "first_name", "last_name", "middle_name", "email", "gender", "occupation",
            "address", "state", "lga", "community", "preferred_language",
        ):
            value = getattr(input, key, None)
            if value is not None:
                fields[key] = value
        if input.date_of_birth:
            from datetime import date

            try:
                fields["date_of_birth"] = date.fromisoformat(input.date_of_birth)
            except ValueError:
                from apps.core.errors import ValidationFailed

                raise ValidationFailed("Date of birth must be YYYY-MM-DD.")
        customer = customer_services.update_customer_profile(
            customer, updated_by=current_user(info), **fields
        )
        return CustomerType.from_model(customer)

    @strawberry.mutation
    def submit_kyc(self, info: Info, input: SubmitKYCInput) -> KYCStatusType:
        customer = current_customer(info)
        profile = kyc_services.submit_kyc(
            customer,
            doc_type=input.doc_type,
            id_number=input.id_number,
            storage_key=input.storage_key,
            submitted_by=current_user(info),
        )
        return KYCStatusType(
            status=profile.status,
            level=profile.level,
            verified_at=str(profile.verified_at) if profile.verified_at else None,
            failure_reason=profile.failure_reason,
        )
