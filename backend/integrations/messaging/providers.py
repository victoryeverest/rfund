"""Messaging provider abstraction (spec §47, §147).

SMS is first-class for rural users (§187). The default `console`
provider logs messages — development only. Production plugs a real
provider (Termii, Twilio, Africa's Talking) by implementing
SMSProvider and setting SMS_PROVIDER.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("rfund.sms")


class SMSProvider:
    code = "abstract"

    def send(self, *, phone: str, message: str) -> str:
        raise NotImplementedError


class ConsoleSMSProvider(SMSProvider):
    """Development provider: logs the SMS (never used in production)."""

    code = "console"

    def send(self, *, phone: str, message: str) -> str:
        logger.info("sms_sent", extra={
            "event": "sms_sent",
            "provider": "console",
            "structured": {"to": phone, "body": message[:160]},
        })
        return "console-logged"


_PROVIDERS: dict[str, type[SMSProvider]] = {"console": ConsoleSMSProvider}


def register_sms_provider(cls):
    _PROVIDERS[cls.code] = cls
    return cls


def _get_sms_provider() -> SMSProvider:
    name = settings.SMS_PROVIDER
    if name not in _PROVIDERS:
        raise KeyError(f"Unknown SMS provider {name!r}")
    return _PROVIDERS[name]()


def send_sms_message(*, phone: str, message: str) -> str:
    return _get_sms_provider().send(phone=phone, message=message)


def send_sms_code(*, phone: str, code: str, purpose: str) -> str:
    # The OTP value only ever reaches the provider call; it is never logged.
    message = f"RFUND verification code: {code}. Valid for a few minutes. Do not share it."
    return _get_sms_provider().send(phone=phone, message=message)
