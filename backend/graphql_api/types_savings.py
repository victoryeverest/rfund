"""Savings GraphQL types (spec §52, §68, §132)."""

from __future__ import annotations

from datetime import date

import strawberry
from strawberry.types import Info

from apps.core.pagination import paginate
from apps.savings import services as savings_services
from apps.savings.models import SavingsGoal, SavingsPlan, SavingsScheduleItem
from apps.core.money import money
from apps.savings.schedules import project_plan
from graphql_api.permissions import current_customer, get_context
from graphql_api.types_common import PageInfo, page_info
from graphql_api.types_customer import CustomerType


@strawberry.type
class SavingsProductType:
    code: str
    name: str
    description: str
    min_contribution: str
    max_contribution: str
    allowed_frequencies: list[str]
    payout_policy: str
    allow_early_payout: bool


@strawberry.type
class ScheduleItemType:
    id: strawberry.ID
    sequence: int
    due_date: str
    amount: str
    status: str
    paid_at: str | None
    payment_reference: str


@strawberry.type
class SavingsPlanType:
    id: strawberry.ID
    reference: str
    product_code: str
    product_name: str
    amount: str
    frequency: str
    start_date: str
    end_date: str
    status: str
    total_contributed: str
    contribution_count: int
    contributions_paid: int
    next_due: ScheduleItemType | None

    @classmethod
    def from_model(cls, plan: SavingsPlan) -> "SavingsPlanType":
        items = plan.schedule_items.count()
        paid = plan.schedule_items.filter(status=SavingsScheduleItem.Status.PAID).count()
        next_item = (
            plan.schedule_items.filter(
                status__in=[SavingsScheduleItem.Status.UPCOMING, SavingsScheduleItem.Status.DUE]
            )
            .order_by("sequence")
            .first()
        )
        return cls(
            id=strawberry.ID(str(plan.pk)),
            reference=plan.reference,
            product_code=plan.product.code,
            product_name=plan.product.name,
            amount=str(plan.amount),
            frequency=plan.frequency,
            start_date=str(plan.start_date),
            end_date=str(plan.end_date),
            status=plan.status,
            total_contributed=str(plan.total_contributed),
            contribution_count=items,
            contributions_paid=paid,
            next_due=_schedule_item(next_item),
        )


def _schedule_item(item) -> ScheduleItemType | None:
    if item is None:
        return None
    return ScheduleItemType(
        id=strawberry.ID(str(item.pk)),
        sequence=item.sequence,
        due_date=str(item.due_date),
        amount=str(item.amount),
        status=item.status,
        paid_at=str(item.paid_at) if item.paid_at else None,
        payment_reference=item.payment_reference,
    )


@strawberry.type
class ScheduleItemConnection:
    items: list[ScheduleItemType]
    page_info: PageInfo


@strawberry.type
class SavingsPlanConnection:
    items: list[SavingsPlanType]
    page_info: PageInfo


@strawberry.type
class SavingsGoalType:
    id: strawberry.ID
    name: str
    description: str
    target_amount: str
    current_amount: str
    target_date: str | None
    contribution_frequency: str
    contribution_amount: str
    status: str
    progress_pct: float

    @classmethod
    def from_model(cls, goal: SavingsGoal) -> "SavingsGoalType":
        progress = float(goal.current_amount / goal.target_amount * 100) if goal.target_amount else 0
        return cls(
            id=strawberry.ID(str(goal.pk)),
            name=goal.name,
            description=goal.description,
            target_amount=str(goal.target_amount),
            current_amount=str(goal.current_amount),
            target_date=str(goal.target_date) if goal.target_date else None,
            contribution_frequency=goal.contribution_frequency,
            contribution_amount=str(goal.contribution_amount),
            status=goal.status,
            progress_pct=round(min(progress, 100.0), 1),
        )


@strawberry.type
class SavingsGoalConnection:
    items: list[SavingsGoalType]
    page_info: PageInfo


@strawberry.type
class PlanProjection:
    contribution_count: int
    total_amount: str
    first_due: str
    last_due: str


@strawberry.input
class CreateSavingsPlanInput:
    product_code: str
    amount: str
    frequency: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD


@strawberry.input
class CreateGoalInput:
    name: str
    target_amount: str
    target_date: str | None = None
    contribution_frequency: str = "MONTHLY"
    contribution_amount: str = "0"


@strawberry.input
class UpdateGoalInput:
    name: str | None = None
    description: str | None = None
    target_amount: str | None = None
    target_date: str | None = None
    contribution_frequency: str | None = None
    contribution_amount: str | None = None


@strawberry.type
class SavingsQueries:
    @strawberry.field
    def savings_products(self, info: Info) -> list[SavingsProductType]:
        out = []
        for p in savings_services.list_products():
            out.append(
                SavingsProductType(
                    code=p.code,
                    name=p.name,
                    description=p.description,
                    min_contribution=str(p.min_contribution),
                    max_contribution=str(p.max_contribution),
                    allowed_frequencies=p.allowed_frequencies or [],
                    payout_policy=p.payout_policy,
                    allow_early_payout=p.allow_early_payout,
                )
            )
        return out

    @strawberry.field
    def savings_plans(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> SavingsPlanConnection:
        customer = current_customer(info)
        qs = SavingsPlan.objects.filter(customer=customer).select_related("product")
        page = paginate(qs, first=first, after=after)
        return SavingsPlanConnection(
            items=[SavingsPlanType.from_model(p) for p in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def savings_plan(self, info: Info, id: strawberry.ID) -> SavingsPlanType:
        customer = current_customer(info)
        plan = savings_services.get_plan(str(id), customer=customer)
        return SavingsPlanType.from_model(plan)

    @strawberry.field
    def savings_schedule(
        self, info: Info, plan_id: strawberry.ID, first: int | None = None, after: str | None = None
    ) -> ScheduleItemConnection:
        customer = current_customer(info)
        plan = savings_services.get_plan(str(plan_id), customer=customer)
        qs = plan.schedule_items.all().order_by("sequence")
        page = paginate(qs, first=first, after=after)
        return ScheduleItemConnection(
            items=[_schedule_item(i) for i in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def savings_goals(
        self, info: Info, first: int | None = None, after: str | None = None
    ) -> SavingsGoalConnection:
        customer = current_customer(info)
        qs = SavingsGoal.objects.filter(customer=customer)
        page = paginate(qs, first=first, after=after)
        return SavingsGoalConnection(
            items=[SavingsGoalType.from_model(g) for g in page.items],
            page_info=page_info(page),
        )

    @strawberry.field
    def savings_projection(
        self,
        info: Info,
        amount: str,
        frequency: str,
        start_date: str,
        end_date: str,
    ) -> PlanProjection:
        """Server-authoritative calculator (spec §21)."""
        from apps.core.errors import ValidationFailed
        from apps.core.money import D

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            value = D(amount)
            if value <= 0:
                raise ValueError("amount must be positive")
        except ValueError:
            raise ValidationFailed("Dates must be YYYY-MM-DD and amount must be positive.")
        projection = project_plan(
            amount=value,
            frequency=frequency,
            start_date=start,
            end_date=end,
        )
        return PlanProjection(
            contribution_count=projection["contribution_count"],
            total_amount=str(money(projection["total_amount"])),
            first_due=str(projection["first_due"]),
            last_due=str(projection["last_due"]),
        )


@strawberry.type
class SavingsMutations:
    @strawberry.mutation
    def create_savings_plan(self, info: Info, input: CreateSavingsPlanInput) -> SavingsPlanType:
        from apps.core.errors import ValidationFailed

        customer = current_customer(info)
        try:
            start = date.fromisoformat(input.start_date)
            end = date.fromisoformat(input.end_date)
        except ValueError:
            raise ValidationFailed("Dates must be YYYY-MM-DD.")
        plan = savings_services.create_savings_plan(
            customer=customer,
            product_code=input.product_code,
            amount=input.amount,
            frequency=input.frequency,
            start_date=start,
            end_date=end,
        )
        return SavingsPlanType.from_model(plan)

    @strawberry.mutation
    def cancel_savings_plan(self, info: Info, plan_id: strawberry.ID) -> SavingsPlanType:
        customer = current_customer(info)
        plan = savings_services.get_plan(str(plan_id), customer=customer)
        plan = savings_services.cancel_savings_plan(plan, actor=current_customer(info).user)
        return SavingsPlanType.from_model(plan)

    @strawberry.mutation
    def create_savings_goal(self, info: Info, input: CreateGoalInput) -> SavingsGoalType:
        customer = current_customer(info)
        target_date = None
        if input.target_date:
            from apps.core.errors import ValidationFailed

            try:
                target_date = date.fromisoformat(input.target_date)
            except ValueError:
                raise ValidationFailed("Target date must be YYYY-MM-DD.")
        goal = savings_services.create_goal(
            customer=customer,
            name=input.name,
            target_amount=input.target_amount,
            target_date=target_date,
            contribution_frequency=input.contribution_frequency,
            contribution_amount=input.contribution_amount,
        )
        return SavingsGoalType.from_model(goal)

    @strawberry.mutation
    def update_savings_goal(
        self, info: Info, goal_id: strawberry.ID, input: UpdateGoalInput
    ) -> SavingsGoalType:
        from apps.core.errors import NotFound

        customer = current_customer(info)
        goal = SavingsGoal.objects.filter(pk=goal_id, customer=customer).first()
        if goal is None:
            raise NotFound("Savings goal not found.")
        fields = {}
        for key in (
            "name", "description", "target_amount", "contribution_frequency",
            "contribution_amount",
        ):
            value = getattr(input, key, None)
            if value is not None:
                fields[key] = value
        if input.target_date:
            from apps.core.errors import ValidationFailed

            try:
                fields["target_date"] = date.fromisoformat(input.target_date)
            except ValueError:
                raise ValidationFailed("Target date must be YYYY-MM-DD.")
        goal = savings_services.update_goal(goal, actor=customer.user, **fields)
        return SavingsGoalType.from_model(goal)

    @strawberry.mutation
    def delete_savings_goal(self, info: Info, goal_id: strawberry.ID) -> bool:
        from apps.core.errors import NotFound

        customer = current_customer(info)
        goal = SavingsGoal.objects.filter(pk=goal_id, customer=customer).first()
        if goal is None:
            raise NotFound("Savings goal not found.")
        savings_services.delete_goal(goal, actor=customer.user)
        return True
