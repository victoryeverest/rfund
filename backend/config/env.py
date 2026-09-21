"""Environment parsing for RFUND.

Deliberately dependency-free: a small, well-tested parser for DATABASE_URL /
REDIS_URL style connection strings so the platform does not depend on
dj-database-url. Only the schemes RFUND actually uses are supported:

    postgres://user:password@host:port/name?sslmode=require
    postgresql://...
    sqlite:///path/to/db.sqlite3

Anything else raises immediately — silent fallbacks are forbidden.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

DJANGO_ENGINES = {
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "sqlite": "django.db.backends.sqlite3",
}


class EnvError(RuntimeError):
    """Raised when required environment configuration is missing or invalid."""


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required and default is None:
            raise EnvError(f"Missing required environment variable: {name}")
        return default
    return raw


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise EnvError(f"Environment variable {name} must be an integer, got: {raw!r}") from exc


@dataclass(frozen=True)
class ParsedDB:
    ENGINE: str
    NAME: str
    USER: str
    PASSWORD: str
    HOST: str
    PORT: str
    OPTIONS: dict


def parse_database_url(url: str) -> ParsedDB:
    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme not in DJANGO_ENGINES:
        raise EnvError(
            f"DATABASE_URL scheme {scheme!r} is not supported. "
            "Use postgres:// or sqlite://"
        )
    if scheme == "sqlite":
        path = unquote(parsed.path)
        if path.startswith("/"):
            path = path[1:]
        if not path:
            raise EnvError("DATABASE_URL for sqlite must include a file path")
        return ParsedDB(
            ENGINE=DJANGO_ENGINES[scheme],
            NAME=path,
            USER="",
            PASSWORD="",
            HOST="",
            PORT="",
            OPTIONS={},
        )
    dbname = unquote(parsed.path)
    if dbname.startswith("/"):
        dbname = dbname[1:]
    if not dbname:
        raise EnvError("DATABASE_URL must include a database name")
    options: dict = {}
    for key, values in parse_qs(parsed.query).items():
        options[key] = values[0]
    return ParsedDB(
        ENGINE=DJANGO_ENGINES[scheme],
        NAME=dbname,
        USER=unquote(parsed.username or ""),
        PASSWORD=unquote(parsed.password or ""),
        HOST=parsed.hostname or "localhost",
        PORT=str(parsed.port or 5432),
        OPTIONS=options,
    )
