"""Identity verification provider registry (spec §12, §150).

Manual review is the default. Real vendor adapters (NIMC/BVN via licensed
partners, SmileID, Youverify, ...) plug in by implementing
IdentityVerificationProvider and registering here.
"""

from __future__ import annotations

from typing import Type

from apps.identity.services import IdentityVerificationProvider

_REGISTRY: dict[str, Type[IdentityVerificationProvider]] = {}


def register(cls: Type[IdentityVerificationProvider]) -> Type[IdentityVerificationProvider]:
    _REGISTRY[cls.code] = cls
    return cls


def get_provider(name: str) -> IdentityVerificationProvider:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown identity provider {name!r}. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()
