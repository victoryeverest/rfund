"""Root schema assembly (spec §52).

One strongly-typed schema organized by domain. Mobile (Flutter) and
future channels consume this same API (§149).
"""

from __future__ import annotations

import strawberry

from graphql_api.types_admin import AdminMutations, AdminQueries
from graphql_api.types_agent import (
    AgentMutations,
    AgentQueries,
    SupportMutations,
    SupportQueries,
)
from graphql_api.types_auth import AuthMutations
from graphql_api.types_customer import MeQueries, ProfileMutations
from graphql_api.types_loans import LoanMutations, LoanQueries
from graphql_api.types_payments import PaymentMutations, PaymentQueries
from graphql_api.types_savings import SavingsMutations, SavingsQueries


@strawberry.type
class Query(
    MeQueries,
    SavingsQueries,
    LoanQueries,
    PaymentQueries,
    AgentQueries,
    SupportQueries,
    AdminQueries,
):
    """All read operations, permission-scoped per field."""


@strawberry.type
class Mutation(
    AuthMutations,
    ProfileMutations,
    SavingsMutations,
    LoanMutations,
    PaymentMutations,
    AgentMutations,
    SupportMutations,
    AdminMutations,
):
    """All write operations, permission-scoped per field."""


schema = strawberry.Schema(query=Query, mutation=Mutation)
