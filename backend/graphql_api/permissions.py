"""Resolver-level authorization helpers (spec §11, §53, §111).

Every protected resolver calls one of these. Object-level checks
(no IDOR) happen in the services via customer scoping.
"""

from __future__ import annotations

from strawberry.types import Info

from apps.accounts.services import require_permission, require_roles
from apps.core.errors import AuthenticationRequired, PermissionDenied
from apps.customers.models import Customer
from apps.customers.services import ensure_customer_profile
from graphql_api.context import GraphQLContext


def get_context(info: Info) -> GraphQLContext:
    return info.context


def current_user(info: Info):
    ctx = info.context
    if ctx.user is None or not ctx.user.is_authenticated:
        raise AuthenticationRequired()
    return ctx.user


def require_auth(info: Info):
    return current_user(info)


def require_perm(info: Info, code: str):
    user = current_user(info)
    require_permission(user, code)
    return user


def require_role(info: Info, *roles: str):
    user = current_user(info)
    require_roles(user, *roles)
    return user


def current_customer(info: Info) -> Customer:
    """The authenticated user's customer profile (creates lazily)."""
    user = current_user(info)
    if not {"CUSTOMER", "AGENT", "ADMIN", "SUPER_ADMIN"}.intersection(user.role_codes()):
        # Agents/admins acting on behalf of a customer pass through explicit ids
        raise PermissionDenied("This action requires a customer profile.")
    return ensure_customer_profile(user)


def owned_customer(info: Info, customer_id: str | None) -> Customer:
    """Fetch a customer, enforcing object-level access (§111).

    Customers may only access themselves; staff need customer.read.
    """
    from apps.customers.services import get_customer

    user = current_user(info)
    target = get_customer(customer_id) if customer_id else ensure_customer_profile(user)
    if target.user_id != user.pk:
        if not user.has_perm_code("customer.read"):
            raise PermissionDenied()
    return target
