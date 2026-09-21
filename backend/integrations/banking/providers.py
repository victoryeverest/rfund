"""Banking provider abstraction (spec §150).

Placeholder architecture for future bank integrations (transfers,
statement verification). No fake functionality: no adapter is
registered until a real partner exists.
"""

from __future__ import annotations


class BankingProvider:
    code = "abstract"

    def name(self) -> str:
        raise NotImplementedError

    def resolve_account(self, *, account_number: str, bank_code: str) -> dict:
        raise NotImplementedError
