"""Top-level ``ohe`` command-line entry point."""

from __future__ import annotations

import click

from ohe import __version__
from ohe.commands.images import images
from ohe.config import resolve_base_url, resolve_settings
from ohe.runtime_api import RuntimeApiClient

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version", prog_name="ohe")
@click.option(
    "--app-url",
    metavar="URL",
    help=(
        "Your OpenHands app URL, e.g. https://app.<your-base-domain>. The "
        "Runtime API URL is derived from it (app -> runtime-api). Falls back to "
        "$OHE_APP_URL or $APP_URL."
    ),
)
@click.option(
    "--runtime-api-url",
    metavar="URL",
    help=(
        "Override the Runtime API base URL for custom hostname layouts, e.g. "
        "https://runtime-api.<your-base-domain>. Falls back to "
        "$OHE_RUNTIME_API_URL or $RUNTIME_API_URL."
    ),
)
@click.option(
    "--api-key",
    metavar="KEY",
    help=(
        "Runtime API key for read operations (optional; derived from the admin "
        "password when omitted). Falls back to $OHE_API_KEY or $API_KEY. This "
        "is the runtime-api key, not a standard OpenHands API key."
    ),
)
@click.option(
    "--admin-password",
    metavar="PASSWORD",
    help=(
        "Runtime API admin password — the 'Runtime API Admin Password' from the "
        "installer config. Used for writes and to derive an API key for reads. "
        "Falls back to $OHE_ADMIN_PASSWORD or $ADMIN_PASSWORD."
    ),
)
@click.pass_context
def main(
    ctx: click.Context,
    app_url: str | None,
    runtime_api_url: str | None,
    api_key: str | None,
    admin_password: str | None,
) -> None:
    """Operate OpenHands Enterprise from the command line.

    Supply your standard app URL (--app-url); the Runtime API URL is derived
    from it. Use --runtime-api-url only for custom hostname layouts. The Runtime
    API credential is separate from the standard OpenHands API token.
    """
    settings = resolve_settings(
        app_url=app_url,
        runtime_api_url=runtime_api_url,
        api_key=api_key,
        admin_password=admin_password,
    )
    ctx.obj = settings


def build_client(ctx: click.Context) -> RuntimeApiClient:
    """Construct a Runtime API client from resolved settings, or exit cleanly."""
    settings = ctx.obj
    try:
        base_url = resolve_base_url(settings)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    return RuntimeApiClient(
        base_url,
        api_key=settings.api_key,
        admin_password=settings.admin_password,
    )


main.add_command(images)


if __name__ == "__main__":
    main()
