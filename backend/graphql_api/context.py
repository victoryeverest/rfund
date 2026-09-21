"""GraphQL execution context + actor resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.http import HttpRequest

from apps.accounts.models import AuthToken, User
from apps.core.errors import AuthenticationRequired

logger = logging.getLogger("rfund.graphql")


@dataclass
class GraphQLContext:
    request: HttpRequest
    user: User | None = None
    token: AuthToken | None = None
    ip_address: str | None = None
    device_id: str = ""
    rate_bucket: str = "anonymous"
    _permissions_cache: set | None = field(default=None, repr=False)

    @property
    def actor(self) -> User:
        if self.user is None or not self.user.is_authenticated:
            raise AuthenticationRequired()
        return self.user


def build_context(request: HttpRequest) -> GraphQLContext:
    from apps.accounts.services import resolve_token

    user = None
    token = None
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        raw = header[7:].strip()
        if raw:
            try:
                user = resolve_token(raw)
                from apps.accounts.models import AuthToken

                token = AuthToken.objects.filter(token_hash=AuthToken.hash_token(raw)).first()
            except AuthenticationRequired:
                user = None  # anonymous; protected resolvers will enforce

    role_class = "anonymous"
    if user is not None:
        roles = user.role_codes()
        if any(r in ("ADMIN", "SUPER_ADMIN") for r in roles):
            role_class = "admin"
        elif "AGENT" in roles:
            role_class = "agent"
        else:
            role_class = "customer"

    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")

    return GraphQLContext(
        request=request,
        user=user,
        token=token,
        ip_address=ip,
        device_id=request.headers.get("X-Device-ID", ""),
        rate_bucket=role_class,
    )
