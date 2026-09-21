"""Settings entrypoint — selects the module for DJANGO_ENV.

Kept as a tiny dispatcher so DJANGO_SETTINGS_MODULE stays constant
("config.settings") across environments, reducing misconfiguration risk.

`pytest` invocations always select the test settings regardless of
DJANGO_ENV, so tests can never accidentally run against dev/prod config.
"""

import os
import sys

from config.env import EnvError

_env = os.environ.get("DJANGO_ENV", "development")

_running_pytest = (
    "pytest" in os.path.basename(sys.argv[0])
    or any("pytest" in os.path.basename(str(a)) for a in sys.argv[1:1])
    or any("pytest" in arg for arg in sys.argv)
)

if _running_pytest or _env == "test":
    from config.settings.test import *  # noqa: F401,F403
elif _env == "production":
    from config.settings.prod import *  # noqa: F401,F403
else:
    from config.settings.dev import *  # noqa: F401,F403

if _env not in {"development", "test", "production"}:
    raise EnvError(f"Invalid DJANGO_ENV: {_env!r}")
