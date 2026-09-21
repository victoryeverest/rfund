"""Cursor pagination for GraphQL connections (spec §55, §100).

Opaque cursors = base64("offset:N"): small, auditable, index-friendly.
Pagination caps are enforced so no client can request unbounded lists.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from django.conf import settings
from django.db.models import QuerySet

from apps.core.errors import ValidationFailed

T = TypeVar("T")


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"offset:{offset}".encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        kind, _, value = raw.partition(":")
        if kind != "offset" or not value.isdigit():
            raise ValueError
        return int(value)
    except ValueError as exc:
        raise ValidationFailed("The pagination cursor is not valid.") from exc


@dataclass
class Page(Generic[T]):
    items: list[T] = field(default_factory=list)
    total_count: int = 0
    has_next_page: bool = False
    has_previous_page: bool = False
    next_cursor: str | None = None
    previous_cursor: str | None = None


def paginate(
    queryset: QuerySet[T],
    first: int | None = None,
    after: str | None = None,
    last: int | None = None,
    before: str | None = None,
) -> Page[T]:
    """Paginate a queryset with hard page-size caps."""
    if first is not None and last is not None:
        raise ValidationFailed("Provide either `first` or `last`, not both.")
    page_size = first if first is not None else last
    if page_size is None:
        page_size = settings.GRAPHQL_DEFAULT_PAGE_SIZE
    if page_size < 1:
        raise ValidationFailed("Page size must be at least 1.")
    if page_size > settings.GRAPHQL_MAX_PAGE_SIZE:
        raise ValidationFailed(
            f"Page size cannot exceed {settings.GRAPHQL_MAX_PAGE_SIZE}."
        )

    total = queryset.count()
    offset = _decode_cursor(after) if after else _decode_cursor(before) if before else 0
    if offset < 0 or offset > total:
        offset = min(max(offset, 0), total)

    items = list(queryset[offset : offset + page_size])
    end = offset + len(items)
    return Page(
        items=items,
        total_count=total,
        has_next_page=end < total,
        has_previous_page=offset > 0,
        next_cursor=_encode_cursor(end) if end < total else None,
        previous_cursor=_encode_cursor(max(offset - page_size, 0)) if offset > 0 else None,
    )
