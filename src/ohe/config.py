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
from urllib.parse import urlsplit, urlunsplit


@dataclass
class RuntimeApiSettings:
    app_url: str | None
    runtime_api_url: str | None
    api_key: str | None
    admin_password: str | None


def _first(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def derive_runtime_api_url(app_url: str) -> str:
    """Derive the Runtime API URL from a standard OpenHands app URL.

    ``https://app.example.com`` -> ``https://runtime-api.example.com``. Scheme
    and port are preserved; any path is dropped. Raises ``ValueError`` when the
    host is not the standard ``app.<base-domain>`` layout, since only an
    override can be correct then.
    """
    raw = app_url.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    host = parts.hostname
    if not host:
        raise ValueError(f"Could not parse a hostname from app URL {app_url!r}.")
    labels = host.split(".")
    if labels[0] != "app" or len(labels) < 2:
        raise ValueError(
            f"App host {host!r} is not the standard 'app.<base-domain>' layout. "
            "Pass --runtime-api-url (or $OHE_RUNTIME_API_URL) explicitly."
        )
    new_host = ".".join(["runtime-api", *labels[1:]])
    netloc = f"{new_host}:{parts.port}" if parts.port else new_host
    return urlunsplit((parts.scheme or "https", netloc, "", "", ""))


def resolve_settings(
    *,
    app_url: str | None = None,
    runtime_api_url: str | None = None,
    api_key: str | None = None,
    admin_password: str | None = None,
    environ: dict | None = None,
) -> RuntimeApiSettings:
    env = environ if environ is not None else os.environ
    return RuntimeApiSettings(
        app_url=_first(app_url, env.get("OHE_APP_URL"), env.get("APP_URL")),
        runtime_api_url=_first(
            runtime_api_url,
            env.get("OHE_RUNTIME_API_URL"),
            env.get("RUNTIME_API_URL"),
        ),
        api_key=_first(api_key, env.get("OHE_API_KEY"), env.get("API_KEY")),
        admin_password=_first(
            admin_password,
            env.get("OHE_ADMIN_PASSWORD"),
            env.get("ADMIN_PASSWORD"),
        ),
    )


def resolve_base_url(settings: RuntimeApiSettings) -> str:
    """Return the effective Runtime API base URL, or raise ``ValueError``.

    An explicit Runtime API URL wins; otherwise it is derived from the app URL.
    """
    if settings.runtime_api_url:
        return settings.runtime_api_url.rstrip("/")
    if settings.app_url:
        return derive_runtime_api_url(settings.app_url)
    raise ValueError(
        "No app or Runtime API URL configured. Pass --app-url "
        "(https://app.<your-base-domain>) or, for a custom layout, "
        "--runtime-api-url. Env: $OHE_APP_URL or $OHE_RUNTIME_API_URL."
    )
