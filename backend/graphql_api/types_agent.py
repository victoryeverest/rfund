"""Agent GraphQL types (spec §70, §129) + support tickets."""

from __future__ import annotations

import strawberry
from strawberry.types import Info

from apps.agents import services as agent_services
from apps.agents.models import Agent, AgentTransaction
from apps.core.pagination import paginate
from apps.customers import services as customer_services
from apps.customers.models import Customer
from apps.support import services as support_services
from apps.support.models import SupportTicket
from graphql_api.permissions import current_customer, current_user, get_context
from graphql_api.types_common import PageInfo, page_info
from graphql_api.types_customer import CustomerType


@strawberry.type
class AgentType:
    id: strawberry.ID
    agent_code: str
    business_name: str
    status: str
    territory_code: str
    territory_state: str
    float_balance: str
    pending_settlements: int


@strawberry.type
class AgentSavingsPlanType:
    """Brief savings-plan info for plan-targeted agent collections."""

    id: strawberry.ID
    reference: str
    product_name: str
    frequency: str
    amount: str
    status: str


@strawberry.type
class AgentTransactionType:
    id: strawberry.ID
    reference: str
    txn_type: str
    amount: str
    status: str
    customer_name: str
    customer_reference: str
    performed_at: str

    @classmethod
    def from_model(cls, t: AgentTransaction) -> "AgentTransactionType":
        return cls(
            id=strawberry.ID(str(t.pk)),
            reference=t.reference,
            txn_type=t.txn_type,
            amount=str(t.amount),
            status=t.status,
            customer_name=t.customer.full_name,
            customer_reference=t.customer.customer_reference,
            performed_at=str(t.performed_at),
        )


@strawberry.type
class AgentTransactionConnection:
    items: list[AgentTransactionType]
    page_info: PageInfo


@strawberry.type
class AgentSettlementType:
    id: strawberry.ID
    reference: str
    amount: str
    status: str
    requested_at: str | None
    settled_at: str | None


@strawberry.type
class AgentDashboard:
    agent: AgentType
    today_collections: str
    today_transactions: int
    available_float: str


@strawberry.input
class AgentCashCollectionInput:
    customer_id: strawberry.ID
    amount: str
    purpose: str = "SAVINGS_CONTRIBUTION"
    target_plan_id: strawberry.ID | None = None
    idempotency_key: str = ""
    client_reference: str = ""
    device_fingerprint: str = ""


@strawberry.input
class AgentPayoutInput:
    customer_id: strawberry.ID
    amount: str
    idempotency_key: str = ""
    device_fingerprint: str = ""


@strawberry.type
class SupportTicketType:
    id: strawberry.ID
    reference: str
    category: str
    subject: str
    status: str
    priority: str
    created_at: str
    message_count: int

    @classmethod
    def from_model(cls, t: SupportTicket) -> "SupportTicketType":
        return cls(
            id=strawberry.ID(str(t.pk)),
            reference=t.reference,
            category=t.category,
            subject=t.subject,
            status=t.status,
            priority=t.priority,
            created_at=str(t.created_at),
            message_count=t.messages.count(),
        )


@strawberry.type
class SupportTicketConnection:
    items: list[SupportTicketType]
    page_info: PageInfo


@strawberry.type
class SupportMessageType:
    id: strawberry.ID
    body: str
    internal: bool
    sender_name: str
    created_at: str


@strawberry.type
class AgentQueries:
    @strawberry.field
    def agent_profile(self, info: Info) -> AgentType:
        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        return _agent_type(agent)

    @strawberry.field
    def agent_dashboard(self, info: Info) -> AgentDashboard:
        from datetime import datetime, timezone as tz
        from decimal import Decimal

        from django.db.models import Sum

        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        day_start = datetime.now(tz=tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_coll = (
            AgentTransaction.objects.filter(
                agent=agent,
                txn_type="CASH_COLLECTION",
                status="SUCCESS",
                performed_at__gte=day_start,
            ).aggregate(t=Sum("amount"))["t"]
            or Decimal("0")
        )
        today_count = AgentTransaction.objects.filter(
            agent=agent, performed_at__gte=day_start
        ).count()
        return AgentDashboard(
            agent=_agent_type(agent),
            today_collections=str(today_coll),
            today_transactions=today_count,
            available_float=str(agent_services.agent_float_balance(agent)),
        )

    @strawberry.field
    def agent_customers(
        self, info: Info, search: str | None = None, first: int | None = None, after: str | None = None
    ) -> "AgentCustomerConnection":
        """Quick customer search for agents (§70)."""
        from django.db.models import Q

        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        qs = Customer.objects.filter(status=Customer.Status.ACTIVE).order_by("first_name")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(customer_reference__icontains=search)
            )
        page = paginate(qs, first=first, after=after)
        return AgentCustomerConnection(
            items=[CustomerType.from_model(c) for c in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def agent_customer_plans(
        self, info: Info, customer_id: strawberry.ID
    ) -> list[AgentSavingsPlanType]:
        """Active savings plans of a customer (for plan-targeted collections)."""
        user = current_user(info)
        agent_services.get_agent_by_user(user)
        customer = customer_services.get_customer(str(customer_id))
        from apps.savings.models import SavingsPlan

        plans = SavingsPlan.objects.filter(
            customer=customer, status=SavingsPlan.Status.ACTIVE
        ).order_by("created_at")
        return [
            AgentSavingsPlanType(
                id=str(p.pk),
                reference=p.reference,
                product_name=p.product.name,
                frequency=p.frequency,
                amount=str(p.amount),
                status=p.status,
            )
            for p in plans
        ]

    @strawberry.field
    def agent_transactions(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> AgentTransactionConnection:
        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        qs = (
            AgentTransaction.objects.filter(agent=agent)
            .select_related("customer")
            .order_by("-performed_at")
        )
        page = paginate(qs, first=first, after=after)
        return AgentTransactionConnection(
            items=[AgentTransactionType.from_model(t) for t in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def agent_settlements(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> list[AgentSettlementType]:
        from apps.agents.models import AgentSettlement

        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        qs = AgentSettlement.objects.filter(agent=agent).order_by("-created_at")
        page = paginate(qs, first=first, after=after)
        return [
            AgentSettlementType(
                id=strawberry.ID(str(s.pk)),
                reference=s.reference,
                amount=str(s.amount),
                status=s.status,
                requested_at=str(s.requested_at) if s.requested_at else None,
                settled_at=str(s.settled_at) if s.settled_at else None,
            )
            for s in page.items
        ]


@strawberry.type
class AgentCustomerConnection:
    items: list[CustomerType]
    page_info: PageInfo


def _agent_type(agent: Agent) -> AgentType:
    from apps.agents.models import AgentSettlement

    return AgentType(
        id=strawberry.ID(str(agent.pk)),
        agent_code=agent.agent_code,
        business_name=agent.business_name,
        status=agent.status,
        territory_code=agent.territory.code,
        territory_state=agent.territory.state,
        float_balance=str(agent_services.agent_float_balance(agent)),
        pending_settlements=AgentSettlement.objects.filter(
            agent=agent,
            status__in=["PENDING_SETTLEMENT", "SETTLEMENT_REQUESTED", "UNDER_REVIEW", "APPROVED"],
        ).count(),
    )


@strawberry.type
class SupportQueries:
    @strawberry.field
    def support_tickets(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> SupportTicketConnection:
        customer = current_customer(info)
        qs = SupportTicket.objects.filter(customer=customer)
        page = paginate(qs, first=first, after=after)
        return SupportTicketConnection(
            items=[SupportTicketType.from_model(t) for t in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def support_ticket(self, info: Info, id: strawberry.ID) -> SupportTicketType:
        customer = current_customer(info)
        ticket = support_services.get_ticket(str(id), customer=customer)
        return SupportTicketType.from_model(ticket)

    @strawberry.field
    def support_messages(self, info: Info, ticket_id: strawberry.ID) -> list[SupportMessageType]:
        customer = current_customer(info)
        ticket = support_services.get_ticket(str(ticket_id), customer=customer)
        user = current_user(info)
        out = []
        for m in ticket.messages.select_related("sender").order_by("created_at"):
            if m.internal and not user.has_perm_code("support.read"):
                continue
            out.append(
                SupportMessageType(
                    id=strawberry.ID(str(m.pk)),
                    body=m.body,
                    internal=m.internal,
                    sender_name=str(m.sender) if m.sender else "Customer",
                    created_at=str(m.created_at),
                )
            )
        return out


@strawberry.input
class CreateTicketInput:
    category: str
    subject: str
    body: str


@strawberry.input
class ReplyTicketInput:
    ticket_id: strawberry.ID
    body: str


@strawberry.type
class AgentMutations:
    @strawberry.mutation
    def agent_cash_collection(
        self, info: Info, input: AgentCashCollectionInput
    ) -> AgentTransactionType:
        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        customer = customer_services.get_customer(str(input.customer_id))
        device = None
        if input.device_fingerprint:
            device = agent_services.register_device(agent, fingerprint=input.device_fingerprint)
        target = {}
        if input.target_plan_id:
            target["plan_id"] = str(input.target_plan_id)
        txn = agent_services.agent_cash_collection(
            agent=agent,
            customer=customer,
            amount=input.amount,
            purpose=input.purpose,
            target=target,
            device=device,
            idempotency_key=input.idempotency_key,
            client_reference=input.client_reference,
        )
        return AgentTransactionType.from_model(txn)

    @strawberry.mutation
    def agent_customer_payout(
        self, info: Info, input: AgentPayoutInput
    ) -> AgentTransactionType:
        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        customer = customer_services.get_customer(str(input.customer_id))
        device = None
        if input.device_fingerprint:
            device = agent_services.register_device(agent, fingerprint=input.device_fingerprint)
        txn = agent_services.agent_customer_payout(
            agent=agent,
            customer=customer,
            amount=input.amount,
            device=device,
            idempotency_key=input.idempotency_key,
        )
        return AgentTransactionType.from_model(txn)

    @strawberry.mutation
    def request_agent_settlement(self, info: Info, amount: str | None = None) -> AgentSettlementType:
        user = current_user(info)
        agent = agent_services.get_agent_by_user(user)
        settlement = agent_services.request_agent_settlement(
            agent, amount=amount, requested_by=user
        )
        return AgentSettlementType(
            id=strawberry.ID(str(settlement.pk)),
            reference=settlement.reference,
            amount=str(settlement.amount),
            status=settlement.status,
            requested_at=str(settlement.requested_at) if settlement.requested_at else None,
            settled_at=None,
        )


@strawberry.type
class SupportMutations:
    @strawberry.mutation
    def create_support_ticket(self, info: Info, input: CreateTicketInput) -> SupportTicketType:
        customer = current_customer(info)
        ticket = support_services.create_ticket(
            customer=customer,
            category=input.category,
            subject=input.subject,
            body=input.body,
            created_by=customer.user,
        )
        return SupportTicketType.from_model(ticket)

    @strawberry.mutation
    def reply_support_ticket(self, info: Info, input: ReplyTicketInput) -> SupportTicketType:
        user = current_user(info)
        customer = current_customer(info)
        ticket = support_services.get_ticket(str(input.ticket_id), customer=customer)
        support_services.reply_ticket(ticket, sender=user, body=input.body)
        return SupportTicketType.from_model(ticket)
