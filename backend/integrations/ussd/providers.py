"""USSD provider abstraction (spec §148).

Architecture only — real gateway adapters register here in the USSD
implementation phase. No fake functionality.
"""

from __future__ import annotations


class USSDProvider:
    code = "abstract"

    def send(self, *, msisdn: str, text: str, session_id: str) -> dict:
        raise NotImplementedError
