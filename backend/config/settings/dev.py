"""Development settings — inherits base; sandbox/dev defaults."""

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import BASE_DIR

# Local sandbox: allow the deterministic payment provider when Paystack
# keys are absent. Never active in production (hard-refused in base).
if not PAYSTACK_SECRET_KEY:
    PAYMENT_PROVIDER = "local"
