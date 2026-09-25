"""Top-level ``ohe`` command-line entry point."""

from __future__ import annotations

import click

from ohe import __version__
from ohe.commands.images import images
from ohe.config import resolve_settings
from ohe.runtime_api import RuntimeApiClient

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version", prog_name="ohe")
@click.option(
    "--runtime-api-url",
    metavar="URL",
    help=(
        "Runtime API base URL, e.g. https://runtime-api.<your-base-domain>. "
        "Falls back to $OHE_RUNTIME_API_URL or $RUNTIME_API_URL."
    ),
)
@click.option(
    "--api-key",
    metavar="KEY",
    help=(
        "Runtime API key used for read operations. Falls back to $OHE_API_KEY "
        "or $API_KEY. This is the runtime-api key, not a standard OpenHands "
        "API key."
    ),
)
@click.option(
    "--admin-password",
    metavar="PASSWORD",
    help=(
        "Runtime API admin password used for write operations. Falls back to "
        "$OHE_ADMIN_PASSWORD or $ADMIN_PASSWORD."
    ),
)
@click.pass_context
def main(
    ctx: click.Context,
    runtime_api_url: str | None,
    api_key: str | None,
    admin_password: str | None,
) -> None:
    """Operate OpenHands Enterprise from the command line.

    Credentials for the Runtime API can be passed as options or through
    environment variables. The Runtime API credential is separate from the
    standard OpenHands API token.
    """
    settings = resolve_settings(
        base_url=runtime_api_url,
        api_key=api_key,
        admin_password=admin_password,
    )
    ctx.obj = settings


def build_client(ctx: click.Context) -> RuntimeApiClient:
    """Construct a Runtime API client from resolved settings, or exit cleanly."""
    settings = ctx.obj
    if not settings.base_url:
        raise click.UsageError(
            "No Runtime API URL configured. Pass --runtime-api-url or set "
            "$OHE_RUNTIME_API_URL (e.g. https://runtime-api.<your-base-domain>)."
        )
    return RuntimeApiClient(
        settings.base_url,
        api_key=settings.api_key,
        admin_password=settings.admin_password,
    )


main.add_command(images)


if __name__ == "__main__":
    main()
