"""Shared GraphQL scalars, enums, and payload shapes."""

from __future__ import annotations

from typing import NewType

import strawberry

# Money crosses the wire as exact decimal strings — never float (§3.3, §179)
Decimal = strawberry.scalar(
    NewType("Decimal", str),
    serialize=lambda v: str(v),
    parse_value=lambda v: v,
    description="Exact decimal money value serialized as a string.",
)


def serialize_decimal(value) -> str:
    return str(value)


# Reusable pagination payload — simple and mobile-friendly (§100)
@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    next_cursor: str | None
    previous_cursor: str | None
    total_count: int


def page_info(page) -> PageInfo:
    return PageInfo(
        has_next_page=page.has_next_page,
        has_previous_page=page.has_previous_page,
        next_cursor=page.next_cursor,
        previous_cursor=page.previous_cursor,
        total_count=page.total_count,
    )


@strawberry.type
class ApiError:
    code: str
    message: str


@strawberry.type
class SuccessPayload:
    success: bool = True
    message: str = ""
