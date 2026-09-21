"""Payments + transactions GraphQL types (spec §52, §72, §134)."""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.core.pagination import paginate
from apps.payments import services as payment_services
from apps.payments.models import Payment
from graphql_api.permissions import current_customer, get_context
from graphql_api.types_common import PageInfo, page_info


@strawberry.type
class PaymentType:
    id: strawberry.ID
    reference: str
    purpose: str
    amount: str
    currency: str
    status: str
    method: str
    provider: str
    provider_reference: str
    created_at: str
    completed_at: str | None

    @classmethod
    def from_model(cls, p: Payment) -> "PaymentType":
        return cls(
            id=strawberry.ID(str(p.pk)),
            reference=p.reference,
            purpose=p.purpose,
            amount=str(p.amount),
            currency=p.currency,
            status=p.status,
            method=p.method,
            provider=p.provider,
            provider_reference=p.provider_reference,
            created_at=str(p.created_at),
            completed_at=str(p.completed_at) if p.completed_at else None,
        )


@strawberry.type
class PaymentConnection:
    items: list[PaymentType]
    page_info: PageInfo


@strawberry.type
class InitializePaymentPayload:
    payment: PaymentType
    authorization_url: str


@strawberry.input
class MakePaymentInput:
    purpose: str  # SAVINGS_CONTRIBUTION | GOAL_FUNDING | LOAN_REPAYMENT | ACCOUNT_FUNDING
    amount: str
    target_plan_id: strawberry.ID | None = None
    target_goal_id: strawberry.ID | None = None
    target_loan_id: strawberry.ID | None = None
    idempotency_key: str = ""
    channels: list[str] | None = None


@strawberry.type
class PaymentQueries:
    @strawberry.field
    def payments(
        self,
        info: Info,
        first: int | None = None,
        after: str | None = None,
        status: str | None = None,
        purpose: str | None = None,
    ) -> PaymentConnection:
        customer = current_customer(info)
        qs = Payment.objects.filter(customer=customer).order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        if purpose:
            qs = qs.filter(purpose=purpose)
        page = paginate(qs, first=first, after=after)
        return PaymentConnection(
            items=[PaymentType.from_model(p) for p in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def payment(self, info: Info, id: strawberry.ID) -> PaymentType:
        customer = current_customer(info)
        payment = payment_services.get_payment(str(id))
        if payment.customer_id != customer.pk:
            from apps.core.errors import NotFound

            raise NotFound("Payment not found.")  # object-level authz
        return PaymentType.from_model(payment)


@strawberry.type
class PaymentMutations:
    @strawberry.mutation
    def make_payment(self, info: Info, input: MakePaymentInput) -> InitializePaymentPayload:
        """Initialize a payment with the configured provider (server-side)."""
        customer = current_customer(info)
        target: dict = {}
        if input.target_plan_id:
            target["plan_id"] = str(input.target_plan_id)
        if input.target_goal_id:
            target["goal_id"] = str(input.target_goal_id)
        if input.target_loan_id:
            target["loan_id"] = str(input.target_loan_id)
        payment, url = payment_services.initialize_payment(
            customer=customer,
            purpose=input.purpose,
            amount=input.amount,
            target=target,
            idempotency_key=input.idempotency_key,
            initiated_by=customer.user,
            device_id=get_context(info).device_id,
            channels=input.channels,
        )
        from apps.fraud.services import check_payment_patterns

        check_payment_patterns(payment)
        return InitializePaymentPayload(
            payment=PaymentType.from_model(payment),
            authorization_url=url,
        )

    @strawberry.mutation
    def verify_payment(self, info: Info, payment_id: strawberry.ID) -> PaymentType:
        """Server-side verification is authoritative (§23)."""
        customer = current_customer(info)
        payment = payment_services.get_payment(str(payment_id))
        if payment.customer_id != customer.pk:
            from apps.core.errors import NotFound

            raise NotFound("Payment not found.")
        payment = payment_services.verify_and_settle(payment)
        return PaymentType.from_model(payment)
