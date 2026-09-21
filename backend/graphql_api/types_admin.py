"""Admin GraphQL types (spec §71, §116, §130).

Admin fields only appear meaningful with permissions — every resolver
checks granular permission codes (§11). Customers can never discover
admin data through the schema (§116): resolvers raise FORBIDDEN.
"""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.agents import services as agent_services
from apps.agents.models import Agent, AgentSettlement
from apps.audit.models import AuditEvent
from apps.core.pagination import paginate
from apps.customers import services as customer_services
from apps.customers.models import Customer
from apps.fraud import services as fraud_services
from apps.fraud.models import FraudAlert
from apps.identity import services as kyc_services
from apps.identity.models import KYCProfile
from apps.ledger import services as ledger_services
from apps.ledger.models import LedgerAccount, LedgerTransaction
from apps.loans import services as loan_services
from apps.loans.models import Loan, LoanApplication
from apps.payments.models import Payment, PaymentWebhookEvent
from apps.reporting import services as reporting_services
from apps.settlements import services as recon_services
from apps.settlements.models import ReconciliationException, ReconciliationRun
from apps.support.models import SupportTicket
from graphql_api.permissions import require_perm
from graphql_api.types_common import PageInfo, page_info


@strawberry.type
class AdminDashboardType:
    active_customers: int
    new_customers_7d: int
    savings_balance: str
    active_savings_plans: int
    loan_portfolio: str
    active_loans: int
    repayment_volume_30d: str
    interest_income: str
    pending_kyc: int
    pending_loan_applications: int
    payment_failures_24h: int
    reconciliation_exceptions: int
    active_agents: int
    agent_collections_today: str
    open_fraud_alerts: int
    open_support_tickets: int


@strawberry.type
class AdminCustomerType:
    id: strawberry.ID
    customer_reference: str
    full_name: str
    phone: str
    email: str
    state: str
    lga: str
    community: str
    status: str
    kyc_tier: str
    created_at: str

    @classmethod
    def from_model(cls, c: Customer) -> "AdminCustomerType":
        return cls(
            id=strawberry.ID(str(c.pk)),
            customer_reference=c.customer_reference,
            full_name=c.full_name,
            phone=c.phone,
            email=c.email,
            state=c.state,
            lga=c.lga,
            community=c.community,
            status=c.status,
            kyc_tier=c.kyc_tier,
            created_at=str(c.created_at),
        )


@strawberry.type
class AdminCustomerConnection:
    items: list[AdminCustomerType]
    page_info: PageInfo


@strawberry.type
class AdminKYCType:
    id: strawberry.ID
    customer_id: strawberry.ID
    customer_name: str
    customer_reference: str
    status: str
    level: str
    submitted_doc_type: str
    created_at: str


@strawberry.type
class AdminKYCConnection:
    items: list[AdminKYCType]
    page_info: PageInfo


@strawberry.type
class AdminLoanApplicationType:
    id: strawberry.ID
    reference: str
    customer_name: str
    customer_reference: str
    product_name: str
    amount_requested: str
    term_months: int
    state: str
    risk_score: str | None
    risk_decision: str | None
    created_at: str

    @classmethod
    def from_model(cls, a: LoanApplication) -> "AdminLoanApplicationType":
        assessment = getattr(a, "assessment", None)
        return cls(
            id=strawberry.ID(str(a.pk)),
            reference=a.reference,
            customer_name=a.customer.full_name,
            customer_reference=a.customer.customer_reference,
            product_name=a.product.name,
            amount_requested=str(a.amount_requested),
            term_months=a.term_months,
            state=a.state,
            risk_score=str(assessment.score) if assessment else None,
            risk_decision=assessment.decision if assessment else None,
            created_at=str(a.created_at),
        )


@strawberry.type
class AdminLoanApplicationConnection:
    items: list[AdminLoanApplicationType]
    page_info: PageInfo


@strawberry.type
class AdminLedgerAccountType:
    id: strawberry.ID
    code: str
    name: str
    type: str
    currency: str
    status: str
    balance: str
    last_posted_at: str | None


@strawberry.type
class AdminLedgerEntryType:
    account_code: str
    account_name: str
    direction: str
    amount: str
    currency: str


@strawberry.type
class AdminLedgerTransactionType:
    id: strawberry.ID
    reference: str
    transaction_type: str
    status: str
    currency: str
    description: str
    external_reference: str
    posted_at: str | None
    created_at: str
    entries: list[AdminLedgerEntryType]

    @classmethod
    def from_model(cls, t: LedgerTransaction) -> "AdminLedgerTransactionType":
        return cls(
            id=strawberry.ID(str(t.pk)),
            reference=t.reference,
            transaction_type=t.transaction_type,
            status=t.status,
            currency=t.currency,
            description=t.description.split(" #idem:")[0],
            external_reference=t.external_reference,
            posted_at=str(t.posted_at) if t.posted_at else None,
            created_at=str(t.created_at),
            entries=[
                AdminLedgerEntryType(
                    account_code=e.account.code,
                    account_name=e.account.name,
                    direction=e.direction,
                    amount=str(e.amount),
                    currency=e.currency,
                )
                for e in t.entries.select_related("account")
            ],
        )


@strawberry.type
class AdminLedgerTransactionConnection:
    items: list[AdminLedgerTransactionType]
    page_info: PageInfo


@strawberry.type
class AdminPaymentType:
    id: strawberry.ID
    reference: str
    customer_name: str
    purpose: str
    amount: str
    status: str
    provider: str
    provider_reference: str
    ledger_reference: str | None
    created_at: str

    @classmethod
    def from_model(cls, p: Payment) -> "AdminPaymentType":
        return cls(
            id=strawberry.ID(str(p.pk)),
            reference=p.reference,
            customer_name=p.customer.full_name,
            purpose=p.purpose,
            amount=str(p.amount),
            status=p.status,
            provider=p.provider,
            provider_reference=p.provider_reference,
            ledger_reference=(
                p.ledger_transaction.reference if p.ledger_transaction_id else None
            ),
            created_at=str(p.created_at),
        )


@strawberry.type
class AdminPaymentConnection:
    items: list[AdminPaymentType]
    page_info: PageInfo


@strawberry.type
class AdminWebhookEventType:
    id: strawberry.ID
    provider: str
    event_id: str
    event_type: str
    signature_valid: bool
    processing_status: str
    processing_error: str
    received_at: str


@strawberry.type
class AdminWebhookConnection:
    items: list[AdminWebhookEventType]
    page_info: PageInfo


@strawberry.type
class AdminReconciliationRunType:
    id: strawberry.ID
    provider: str
    period_start: str
    period_end: str
    status: str
    matched_count: int
    exception_count: int
    started_at: str


@strawberry.type
class AdminReconciliationExceptionType:
    id: strawberry.ID
    item_status: str
    internal_reference: str
    provider_reference: str
    internal_amount: str | None
    provider_amount: str | None
    reason: str
    resolution: str
    resolved: bool


@strawberry.type
class AdminAgentType:
    id: strawberry.ID
    agent_code: str
    business_name: str
    phone: str
    status: str
    territory_code: str
    territory_state: str
    float_balance: str
    created_at: str


@strawberry.type
class AdminAgentConnection:
    items: list[AdminAgentType]
    page_info: PageInfo


@strawberry.type
class AdminAgentSettlementType:
    id: strawberry.ID
    reference: str
    agent_code: str
    amount: str
    status: str
    requested_at: str | None
    settled_at: str | None


@strawberry.type
class AdminFraudAlertType:
    id: strawberry.ID
    rule_code: str
    resource_type: str
    resource_id: str
    severity: str
    status: str
    details: str
    created_at: str

    @classmethod
    def from_model(cls, a: FraudAlert) -> "AdminFraudAlertType":
        return cls(
            id=strawberry.ID(str(a.pk)),
            rule_code=a.rule.code,
            resource_type=a.resource_type,
            resource_id=a.resource_id,
            severity=a.severity,
            status=a.status,
            details=str(a.details)[:200],
            created_at=str(a.created_at),
        )


@strawberry.type
class AdminFraudAlertConnection:
    items: list[AdminFraudAlertType]
    page_info: PageInfo


@strawberry.type
class AdminAuditEventType:
    id: strawberry.ID
    actor_label: str
    action: str
    resource_type: str
    resource_id: str
    reason: str
    ip_address: str | None
    occurred_at: str


@strawberry.type
class AdminAuditConnection:
    items: list[AdminAuditEventType]
    page_info: PageInfo


@strawberry.type
class AdminSupportTicketType:
    id: strawberry.ID
    reference: str
    customer_name: str
    category: str
    subject: str
    status: str
    priority: str
    assignee_name: str | None
    created_at: str

    @classmethod
    def from_model(cls, t: SupportTicket) -> "AdminSupportTicketType":
        return cls(
            id=strawberry.ID(str(t.pk)),
            reference=t.reference,
            customer_name=t.customer.full_name,
            category=t.category,
            subject=t.subject,
            status=t.status,
            priority=t.priority,
            assignee_name=str(t.assignee) if t.assignee else None,
            created_at=str(t.created_at),
        )


@strawberry.type
class AdminSupportConnection:
    items: list[AdminSupportTicketType]
    page_info: PageInfo


@strawberry.type
class AdminLoanType:
    id: strawberry.ID
    reference: str
    customer_name: str
    product_name: str
    principal: str
    outstanding_principal: str
    outstanding_interest: str
    status: str
    disbursed_at: str | None

    @classmethod
    def from_model(cls, l: Loan) -> "AdminLoanType":
        return cls(
            id=strawberry.ID(str(l.pk)),
            reference=l.reference,
            customer_name=l.customer.full_name,
            product_name=l.product.name,
            principal=str(l.principal),
            outstanding_principal=str(l.outstanding_principal),
            outstanding_interest=str(l.outstanding_interest),
            status=l.status,
            disbursed_at=str(l.disbursed_at) if l.disbursed_at else None,
        )


@strawberry.type
class AdminQueries:
    @strawberry.field
    def admin_dashboard(self, info: Info) -> AdminDashboardType:
        require_perm(info, "report.view")
        snapshot = reporting_services.admin_dashboard_snapshot()
        return AdminDashboardType(**snapshot)

    # -- Customers -----------------------------------------------------------
    @strawberry.field
    def admin_customers(
        self,
        info: Info,
        search: str | None = None,
        status: str | None = None,
        first: int | None = None,
        after: str | None = None,
    ) -> AdminCustomerConnection:
        require_perm(info, "customer.read")
        from django.db.models import Q

        qs = Customer.objects.all().order_by("-created_at")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(customer_reference__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        page = paginate(qs, first=first, after=after)
        return AdminCustomerConnection(
            items=[AdminCustomerType.from_model(c) for c in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_kyc_queue(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> AdminKYCConnection:
        require_perm(info, "kyc.read")
        qs = KYCProfile.objects.filter(
            status__in=["PENDING", "UNDER_REVIEW"]
        ).select_related("customer")
        page = paginate(qs, first=first, after=after)
        items = []
        for profile in page.items:
            doc = profile.customer.identity_documents.first()
            items.append(
                AdminKYCType(
                    id=strawberry.ID(str(profile.pk)),
                    customer_id=strawberry.ID(str(profile.customer_id)),
                    customer_name=profile.customer.full_name,
                    customer_reference=profile.customer.customer_reference,
                    status=profile.status,
                    level=profile.level,
                    submitted_doc_type=doc.doc_type if doc else "",
                    created_at=str(profile.created_at),
                )
            )
        return AdminKYCConnection(items=items, page_info=page_info(page))

    # -- Loans ---------------------------------------------------------------
    @strawberry.field
    def admin_loan_applications(
        self,
        info: Info,
        state: str | None = None,
        first: int | None = None,
        after: str | None = None,
    ) -> AdminLoanApplicationConnection:
        require_perm(info, "loan.read")
        qs = LoanApplication.objects.select_related(
            "customer", "product", "assessment"
        ).order_by("-created_at")
        if state:
            qs = qs.filter(state=state)
        page = paginate(qs, first=first, after=after)
        return AdminLoanApplicationConnection(
            items=[AdminLoanApplicationType.from_model(a) for a in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_loans(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[AdminLoanType]:
        require_perm(info, "loan.read")
        qs = Loan.objects.select_related("customer", "product").order_by("-created_at")
        page = paginate(qs, first=first, after=after)
        return [AdminLoanType.from_model(l) for l in page.items]

    # -- Payments / webhooks ---------------------------------------------------
    @strawberry.field
    def admin_payments(
        self,
        info: Info,
        status: str | None = None,
        first: int | None = None,
        after: str | None = None,
    ) -> AdminPaymentConnection:
        require_perm(info, "payment.view")
        qs = Payment.objects.select_related("customer").order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        page = paginate(qs, first=first, after=after)
        return AdminPaymentConnection(
            items=[AdminPaymentType.from_model(p) for p in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_webhooks(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> AdminWebhookConnection:
        require_perm(info, "payment.view")
        qs = PaymentWebhookEvent.objects.all().order_by("-received_at")
        page = paginate(qs, first=first, after=after)
        return AdminWebhookConnection(
            items=[
                AdminWebhookEventType(
                    id=strawberry.ID(str(w.pk)),
                    provider=w.provider,
                    event_id=w.event_id,
                    event_type=w.event_type,
                    signature_valid=w.signature_valid,
                    processing_status=w.processing_status,
                    processing_error=w.processing_error,
                    received_at=str(w.received_at),
                )
                for w in page.items
            ],
            page_info=page_info(page),
        )

    # -- Ledger ----------------------------------------------------------------
    @strawberry.field
    def admin_ledger_accounts(self, info: Info) -> list[AdminLedgerAccountType]:
        require_perm(info, "ledger.view")
        return [
            AdminLedgerAccountType(
                id=strawberry.ID(str(a.pk)),
                code=a.code,
                name=a.name,
                type=a.type,
                currency=a.currency,
                status=a.status,
                balance=str(a.balance),
                last_posted_at=str(a.last_posted_at) if a.last_posted_at else None,
            )
            for a in LedgerAccount.objects.all()
        ]

    @strawberry.field
    def admin_ledger_transactions(
        self,
        info: Info,
        first: int | None = None,
        after: str | None = None,
        transaction_type: str | None = None,
    ) -> AdminLedgerTransactionConnection:
        require_perm(info, "ledger.view")
        qs = LedgerTransaction.objects.all().order_by("-created_at")
        if transaction_type:
            qs = qs.filter(transaction_type=transaction_type)
        page = paginate(qs, first=first, after=after)
        return AdminLedgerTransactionConnection(
            items=[AdminLedgerTransactionType.from_model(t) for t in page.items],
            page_info=page_info(page),
        )

    # -- Reconciliation ----------------------------------------------------------
    @strawberry.field
    def admin_reconciliation_runs(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[AdminReconciliationRunType]:
        require_perm(info, "reconciliation.view")
        qs = ReconciliationRun.objects.all().order_by("-started_at")
        page = paginate(qs, first=first, after=after)
        return [
            AdminReconciliationRunType(
                id=strawberry.ID(str(r.pk)),
                provider=r.provider,
                period_start=str(r.period_start),
                period_end=str(r.period_end),
                status=r.status,
                matched_count=r.matched_count,
                exception_count=r.exception_count,
                started_at=str(r.started_at),
            )
            for r in page.items
        ]

    @strawberry.field
    def admin_reconciliation_exceptions(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[AdminReconciliationExceptionType]:
        require_perm(info, "reconciliation.view")
        qs = ReconciliationException.objects.select_related("item").order_by("-created_at")
        page = paginate(qs, first=first, after=after)
        return [
            AdminReconciliationExceptionType(
                id=strawberry.ID(str(e.pk)),
                item_status=e.item.status,
                internal_reference=e.item.internal_reference,
                provider_reference=e.item.provider_reference,
                internal_amount=str(e.item.internal_amount) if e.item.internal_amount is not None else None,
                provider_amount=str(e.item.provider_amount) if e.item.provider_amount is not None else None,
                reason=e.reason,
                resolution=e.resolution,
                resolved=e.resolved_at is not None,
            )
            for e in page.items
        ]

    # -- Agents -------------------------------------------------------------------
    @strawberry.field
    def admin_agents(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> AdminAgentConnection:
        require_perm(info, "agent.read")
        qs = Agent.objects.select_related("territory").order_by("agent_code")
        page = paginate(qs, first=first, after=after)
        return AdminAgentConnection(
            items=[
                AdminAgentType(
                    id=strawberry.ID(str(a.pk)),
                    agent_code=a.agent_code,
                    business_name=a.business_name,
                    phone=a.phone,
                    status=a.status,
                    territory_code=a.territory.code,
                    territory_state=a.territory.state,
                    float_balance=str(agent_services.agent_float_balance(a)),
                    created_at=str(a.created_at),
                )
                for a in page.items
            ],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_agent_settlements(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[AdminAgentSettlementType]:
        require_perm(info, "agent.read")
        qs = AgentSettlement.objects.select_related("agent").order_by("-created_at")
        page = paginate(qs, first=first, after=after)
        return [
            AdminAgentSettlementType(
                id=strawberry.ID(str(s.pk)),
                reference=s.reference,
                agent_code=s.agent.agent_code,
                amount=str(s.amount),
                status=s.status,
                requested_at=str(s.requested_at) if s.requested_at else None,
                settled_at=str(s.settled_at) if s.settled_at else None,
            )
            for s in page.items
        ]

    # -- Fraud / audit / support / reports ------------------------------------------
    @strawberry.field
    def admin_fraud_alerts(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> AdminFraudAlertConnection:
        require_perm(info, "fraud.read")
        qs = FraudAlert.objects.select_related("rule").order_by("-created_at")
        page = paginate(qs, first=first, after=after)
        return AdminFraudAlertConnection(
            items=[AdminFraudAlertType.from_model(a) for a in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_audit_events(
        self,
        info: Info,
        resource_type: str | None = None,
        first: int | None = None,
        after: str | None = None,
    ) -> AdminAuditConnection:
        require_perm(info, "audit.view")
        qs = AuditEvent.objects.all().order_by("-occurred_at")
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        page = paginate(qs, first=first, after=after)
        return AdminAuditConnection(
            items=[
                AdminAuditEventType(
                    id=strawberry.ID(str(e.pk)),
                    actor_label=e.actor_label,
                    action=e.action,
                    resource_type=e.resource_type,
                    resource_id=e.resource_id,
                    reason=e.reason[:200],
                    ip_address=str(e.ip_address) if e.ip_address else None,
                    occurred_at=str(e.occurred_at),
                )
                for e in page.items
            ],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_support_tickets(
        self, info: Info, status: str | None = None, first: int | None = None, after: str | None = None
    ) -> AdminSupportConnection:
        require_perm(info, "support.read")
        qs = SupportTicket.objects.select_related("customer", "assignee").order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        page = paginate(qs, first=first, after=after)
        return AdminSupportConnection(
            items=[AdminSupportTicketType.from_model(t) for t in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def admin_report(self, info: Info, report_type: str) -> str:
        """CSV export (permission-checked, audited §118)."""
        from apps.audit.models import AuditAction, record_audit

        user = require_perm(info, "export.general")
        rows = reporting_services.export_rows(report_type)
        record_audit(
            action=AuditAction.EXPORT,
            resource_type="report",
            resource_id=report_type,
            actor=user,
        )
        return _rows_to_csv(rows)


def _rows_to_csv(rows: list[dict]) -> str:
    import csv
    import io

    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


@strawberry.input
class ReviewKycInput:
    profile_id: strawberry.ID
    decision: str  # APPROVED / REJECTED / INFO_REQUESTED
    reason: str = ""
    new_level: str | None = None


@strawberry.input
class LoanDecisionInput:
    application_id: strawberry.ID
    approve: bool
    reason: str
    amount: str | None = None
    term_months: int | None = None


@strawberry.input
class ResolveReconciliationInput:
    exception_id: strawberry.ID
    resolution: str


@strawberry.input
class ReviewFraudAlertInput:
    alert_id: strawberry.ID
    decision: str  # UNDER_REVIEW / CLEARED / CONFIRMED
    notes: str = ""


@strawberry.type
class AdminMutations:
    @strawberry.mutation
    def review_kyc(self, info: Info, input: ReviewKycInput) -> bool:
        user = require_perm(info, "kyc.review")
        profile = KYCProfile.objects.filter(pk=input.profile_id).first()
        if profile is None:
            from apps.core.errors import NotFound

            raise NotFound("KYC profile not found.")
        kyc_services.review_kyc(
            profile,
            reviewer=user,
            decision=input.decision,
            reason=input.reason,
            new_level=input.new_level,
        )
        return True

    @strawberry.mutation
    def decide_loan_application(self, info: Info, input: LoanDecisionInput) -> AdminLoanApplicationType:
        from apps.core.errors import NotFound

        user = require_perm(info, "loan.review")
        application = LoanApplication.objects.select_related("customer", "product").filter(
            pk=input.application_id
        ).first()
        if application is None:
            raise NotFound("Loan application not found.")
        if input.approve:
            require_perm(info, "loan.approve")
            application = loan_services.approve_application(
                application,
                approver=user,
                reason=input.reason,
                amount=input.amount,
                term_months=input.term_months,
            )
        else:
            application = loan_services.reject_application(
                application, reviewer=user, reason=input.reason
            )
        return AdminLoanApplicationType.from_model(application)

    @strawberry.mutation
    def disburse_loan(self, info: Info, application_id: strawberry.ID) -> AdminLoanApplicationType:
        from apps.core.errors import NotFound

        user = require_perm(info, "loan.disburse")
        application = LoanApplication.objects.select_related("customer", "product").filter(
            pk=application_id
        ).first()
        if application is None:
            raise NotFound("Loan application not found.")
        loan_services.disburse_loan(application, disbursed_by=user)
        application.refresh_from_db()
        return AdminLoanApplicationType.from_model(application)

    @strawberry.mutation
    def reverse_ledger_transaction(
        self, info: Info, transaction_id: strawberry.ID, reason: str
    ) -> AdminLedgerTransactionType:
        user = require_perm(info, "ledger.reverse")
        txn = LedgerTransaction.objects.filter(pk=transaction_id).first()
        if txn is None:
            from apps.core.errors import NotFound

            raise NotFound("Ledger transaction not found.")
        reversal = ledger_services.reverse_transaction(txn, reversed_by=user, reason=reason)
        return AdminLedgerTransactionType.from_model(reversal)

    @strawberry.mutation
    def run_reconciliation(self, info: Info, provider: str = "local") -> AdminReconciliationRunType:
        user = require_perm(info, "reconciliation.resolve")
        run = recon_services.run_reconciliation(provider=provider)
        return AdminReconciliationRunType(
            id=strawberry.ID(str(run.pk)),
            provider=run.provider,
            period_start=str(run.period_start),
            period_end=str(run.period_end),
            status=run.status,
            matched_count=run.matched_count,
            exception_count=run.exception_count,
            started_at=str(run.started_at),
        )

    @strawberry.mutation
    def resolve_reconciliation_exception(
        self, info: Info, input: ResolveReconciliationInput
    ) -> bool:
        user = require_perm(info, "reconciliation.resolve")
        recon_services.resolve_exception(str(input.exception_id), resolver=user, resolution=input.resolution)
        return True

    @strawberry.mutation
    def set_agent_status(
        self, info: Info, agent_id: strawberry.ID, status: str, reason: str = ""
    ) -> bool:
        user = require_perm(info, "agent.manage")
        agent = Agent.objects.filter(pk=agent_id).first()
        if agent is None:
            from apps.core.errors import NotFound

            raise NotFound("Agent not found.")
        agent_services.set_agent_status(agent, status, actor=user, reason=reason)
        return True

    @strawberry.mutation
    def approve_agent_settlement(self, info: Info, settlement_id: strawberry.ID) -> bool:
        user = require_perm(info, "settlement.approve")
        settlement = AgentSettlement.objects.select_related("agent").filter(pk=settlement_id).first()
        if settlement is None:
            from apps.core.errors import NotFound

            raise NotFound("Agent settlement not found.")
        if settlement.status == "SETTLEMENT_REQUESTED":
            agent_services.review_agent_settlement(settlement, reviewer=user, approve=True)
        agent_services.approve_agent_settlement(settlement, approver=user)
        return True

    @strawberry.mutation
    def review_fraud_alert(self, info: Info, input: ReviewFraudAlertInput) -> bool:
        user = require_perm(info, "fraud.manage")
        alert = FraudAlert.objects.filter(pk=input.alert_id).first()
        if alert is None:
            from apps.core.errors import NotFound

            raise NotFound("Fraud alert not found.")
        fraud_services.review_alert(alert, reviewer=user, decision=input.decision, notes=input.notes)
        return True

    @strawberry.mutation
    def set_customer_status(
        self, info: Info, customer_id: strawberry.ID, status: str, reason: str = ""
    ) -> bool:
        user = require_perm(info, "customer.manage")
        customer = customer_services.get_customer(str(customer_id))
        customer_services.set_customer_status(customer, status, actor=user, reason=reason)
        return True
