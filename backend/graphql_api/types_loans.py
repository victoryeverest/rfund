"""Loans GraphQL types (spec §52, §69, §133)."""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.core.pagination import paginate
from apps.loans import services as loan_services
from apps.loans.models import (
    Loan,
    LoanApplication,
    RepaymentScheduleItem,
)
from graphql_api.permissions import current_customer
from graphql_api.types_common import PageInfo, page_info


@strawberry.type
class LoanProductType:
    code: str
    name: str
    description: str
    min_amount: str
    max_amount: str
    term_values: list[int]
    repayment_frequency: str
    interest_method: str
    interest_rate: str


@strawberry.type
class EligibilityType:
    eligible: bool
    reasons: list[str]


@strawberry.type
class RiskFactorType:
    rule: str
    name: str
    score: int
    explanation: str


@strawberry.type
class RiskAssessmentType:
    score: str
    decision: str
    factors: list[RiskFactorType]


@strawberry.type
class LoanOfferType:
    amount: str
    interest_rate: str
    term_months: int
    total_repayable: str
    first_payment_date: str
    expires_on: str
    status: str


@strawberry.type
class RepaymentScheduleItemType:
    sequence: int
    due_date: str
    principal_due: str
    interest_due: str
    fees_due: str
    penalty_due: str
    total_due: str
    amount_paid: str
    status: str


@strawberry.type
class LoanApplicationType:
    id: strawberry.ID
    reference: str
    product_code: str
    product_name: str
    amount_requested: str
    term_months: int
    purpose: str
    state: str
    submitted_at: str | None
    decision_at: str | None
    rejection_reason: str
    offer: LoanOfferType | None
    assessment: RiskAssessmentType | None

    @classmethod
    def from_model(cls, a: LoanApplication) -> "LoanApplicationType":
        offer = None
        if a.offer:
            offer = LoanOfferType(
                amount=str(a.offer.amount),
                interest_rate=str(a.offer.interest_rate),
                term_months=a.offer.term_months,
                total_repayable=str(a.offer.total_repayable),
                first_payment_date=str(a.offer.first_payment_date),
                expires_on=str(a.offer.expires_on),
                status=a.offer.status,
            )
        assessment = None
        if a.assessment:
            assessment = RiskAssessmentType(
                score=str(a.assessment.score),
                decision=a.assessment.decision,
                factors=[
                    RiskFactorType(
                        rule=f.rule_code,
                        name=f.rule_code.replace("_", " ").title(),
                        score=f.score,
                        explanation=f.explanation,
                    )
                    for f in a.assessment.factors.all()
                ],
            )
        return cls(
            id=strawberry.ID(str(a.pk)),
            reference=a.reference,
            product_code=a.product.code,
            product_name=a.product.name,
            amount_requested=str(a.amount_requested),
            term_months=a.term_months,
            purpose=a.purpose,
            state=a.state,
            submitted_at=str(a.submitted_at) if a.submitted_at else None,
            decision_at=str(a.decision_at) if a.decision_at else None,
            rejection_reason=a.rejection_reason,
            offer=offer,
            assessment=assessment,
        )


@strawberry.type
class LoanType:
    id: strawberry.ID
    reference: str
    product_name: str
    principal: str
    interest_rate: str
    term_months: int
    outstanding_principal: str
    outstanding_interest: str
    outstanding_fees: str
    total_outstanding: str
    status: str
    disbursed_at: str | None

    @classmethod
    def from_model(cls, l: Loan) -> "LoanType":
        return cls(
            id=strawberry.ID(str(l.pk)),
            reference=l.reference,
            product_name=l.product.name,
            principal=str(l.principal),
            interest_rate=str(l.interest_rate),
            term_months=l.term_months,
            outstanding_principal=str(l.outstanding_principal),
            outstanding_interest=str(l.outstanding_interest),
            outstanding_fees=str(l.outstanding_fees),
            total_outstanding=str(l.total_outstanding),
            status=l.status,
            disbursed_at=str(l.disbursed_at) if l.disbursed_at else None,
        )


@strawberry.type
class LoanApplicationConnection:
    items: list[LoanApplicationType]
    page_info: PageInfo


@strawberry.type
class RepaymentScheduleConnection:
    items: list[RepaymentScheduleItemType]
    page_info: PageInfo


@strawberry.input
class ApplyForLoanInput:
    product_code: str
    amount: str
    term_months: int
    purpose: str = ""
    business_name: str = ""
    business_type: str = ""
    monthly_income: str = ""
    farm_state: str = ""
    farm_lga: str = ""
    farm_size_hectares: str = ""
    crop: str = ""


@strawberry.type
class LoanQueries:
    @strawberry.field
    def loan_products(self, info: Info) -> list[LoanProductType]:
        out = []
        for p in loan_services.list_products():
            out.append(
                LoanProductType(
                    code=p.code,
                    name=p.name,
                    description=p.description,
                    min_amount=str(p.min_amount),
                    max_amount=str(p.max_amount),
                    term_values=p.term_values or [],
                    repayment_frequency=p.repayment_frequency,
                    interest_method=p.interest_method,
                    interest_rate=str(p.interest_rate),
                )
            )
        return out

    @strawberry.field
    def loan_eligibility(
        self, info: Info, product_code: str, amount: str, term_months: int
    ) -> EligibilityType:
        customer = current_customer(info)
        product = loan_services.get_product(product_code)
        result = loan_services.check_eligibility(customer, product, amount, term_months)
        return EligibilityType(eligible=result["eligible"], reasons=result["reasons"])

    @strawberry.field
    def loan_applications(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> LoanApplicationConnection:
        customer = current_customer(info)
        qs = LoanApplication.objects.filter(customer=customer).select_related(
            "product", "offer", "assessment"
        )
        page = paginate(qs, first=first, after=after)
        return LoanApplicationConnection(
            items=[LoanApplicationType.from_model(a) for a in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def loan_application(self, info: Info, id: strawberry.ID) -> LoanApplicationType:
        customer = current_customer(info)
        app = loan_services.get_application(str(id), customer=customer)
        return LoanApplicationType.from_model(app)

    @strawberry.field
    def loans(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[LoanType]:
        customer = current_customer(info)
        qs = Loan.objects.filter(customer=customer).select_related("product")
        page = paginate(qs, first=first, after=after)
        return [LoanType.from_model(l) for l in page.items]

    @strawberry.field
    def loan(self, info: Info, id: strawberry.ID) -> LoanType:
        from apps.core.errors import NotFound

        customer = current_customer(info)
        loan = Loan.objects.select_related("product").filter(pk=id, customer=customer).first()
        if loan is None:
            raise NotFound("Loan not found.")
        return LoanType.from_model(loan)

    @strawberry.field
    def repayment_schedule(
        self, info: Info, loan_id: strawberry.ID, first: int | None = None, after: str | None = None
    ) -> RepaymentScheduleConnection:
        from apps.core.errors import NotFound

        customer = current_customer(info)
        loan = Loan.objects.filter(pk=loan_id, customer=customer).first()
        if loan is None:
            raise NotFound("Loan not found.")
        qs = loan.repayment_schedule.all().order_by("sequence")
        page = paginate(qs, first=first, after=after)
        return RepaymentScheduleConnection(
            items=[
                RepaymentScheduleItemType(
                    sequence=i.sequence,
                    due_date=str(i.due_date),
                    principal_due=str(i.principal_due),
                    interest_due=str(i.interest_due),
                    fees_due=str(i.fees_due),
                    penalty_due=str(i.penalty_due),
                    total_due=str(i.total_due),
                    amount_paid=str(i.amount_paid),
                    status=i.status,
                )
                for i in page.items
            ],
            page_info=page_info(page),
        )


@strawberry.type
class LoanMutations:
    @strawberry.mutation
    def apply_for_loan(self, info: Info, input: ApplyForLoanInput) -> LoanApplicationType:
        customer = current_customer(info)
        business_info = {
            k: v
            for k, v in {
                "business_name": input.business_name,
                "business_type": input.business_type,
                "monthly_income": input.monthly_income,
                "farm_state": input.farm_state,
                "farm_lga": input.farm_lga,
                "farm_size_hectares": input.farm_size_hectares,
                "crop": input.crop,
            }.items()
            if v
        }
        application = loan_services.create_loan_application(
            customer=customer,
            product_code=input.product_code,
            amount=input.amount,
            term_months=input.term_months,
            purpose=input.purpose,
            business_info=business_info,
        )
        return LoanApplicationType.from_model(application)

    @strawberry.mutation
    def accept_loan_offer(self, info: Info, application_id: strawberry.ID) -> LoanApplicationType:
        customer = current_customer(info)
        application = loan_services.get_application(str(application_id), customer=customer)
        application = loan_services.accept_offer(application, customer=customer)
        return LoanApplicationType.from_model(application)

    @strawberry.mutation
    def reject_loan_offer(self, info: Info, application_id: strawberry.ID) -> LoanApplicationType:
        from apps.core.errors import NotFound, ValidationFailed

        customer = current_customer(info)
        application = loan_services.get_application(str(application_id), customer=customer)
        if application.state != LoanApplication.State.OFFERED:
            raise ValidationFailed("This application has no offer to reject.")
        offer = application.offer
        offer.status = "REJECTED"
        offer.rejected_at = __import__("django.utils.timezone", fromlist=["timezone"]).now()
        offer.save(update_fields=["status", "rejected_at"])
        application.state = LoanApplication.State.CANCELLED
        application.save(update_fields=["state", "updated_at"])
        return LoanApplicationType.from_model(application)
