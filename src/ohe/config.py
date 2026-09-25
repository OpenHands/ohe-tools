"""Resolve Runtime API connection settings from CLI options and environment.

Precedence for each value: explicit CLI option > ``OHE_*`` environment variable
> the bare variable names used by the documented shell script
(``RUNTIME_API_URL``, ``API_KEY``, ``ADMIN_PASSWORD``). The bare names are
accepted so credentials exported for the existing ``warm-runtime-configs.sh``
workflow keep working.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RuntimeApiSettings:
    base_url: str | None
    api_key: str | None
    admin_password: str | None


def _first(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def resolve_settings(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    admin_password: str | None = None,
    environ: dict | None = None,
) -> RuntimeApiSettings:
    env = environ if environ is not None else os.environ
    return RuntimeApiSettings(
        base_url=_first(
            base_url, env.get("OHE_RUNTIME_API_URL"), env.get("RUNTIME_API_URL")
        ),
        api_key=_first(api_key, env.get("OHE_API_KEY"), env.get("API_KEY")),
        admin_password=_first(
            admin_password,
            env.get("OHE_ADMIN_PASSWORD"),
            env.get("ADMIN_PASSWORD"),
        ),
    )
