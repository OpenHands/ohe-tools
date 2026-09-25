"""``ohe images`` — manage custom sandbox images (warm runtime configurations).

Each warm runtime configuration registers one sandbox image with the Runtime
API, which keeps a pool of ready sandboxes for it and exposes it in the user's
Settings -> Application -> Default Sandbox dropdown.
"""

from __future__ import annotations

import json
import sys

import click

from ohe.runtime_api.errors import RuntimeApiError

# Fields the Runtime API requires in a saved configuration body. ``count`` and
# the run-as/fs-group fields are optional and copied from the default template.
_REQUIRED_FIELDS = ("image", "working_dir", "command", "environment")


def _client(ctx: click.Context):
    # Imported here to avoid a circular import with cli.py at module load.
    from ohe.cli import build_client

    return build_client(ctx)


def _run(func):
    """Call a client method, converting API errors into clean CLI failures."""
    try:
        return func()
    except RuntimeApiError as exc:
        raise click.ClickException(str(exc)) from exc


def _echo_json(data) -> None:
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def _echo_table(configs: list[dict]) -> None:
    if not configs:
        click.echo("No warm runtime configurations found.")
        return
    rows = [
        (
            c.get("name", ""),
            c.get("source", ""),
            "" if c.get("count") is None else str(c.get("count")),
            c.get("image", ""),
        )
        for c in configs
    ]
    headers = ("NAME", "SOURCE", "COUNT", "IMAGE")
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    click.echo(line.rstrip())
    for row in rows:
        click.echo("  ".join(row[i].ljust(widths[i]) for i in range(len(row))).rstrip())


@click.group()
def images() -> None:
    """Manage custom sandbox images (warm runtime configurations)."""


@images.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.pass_context
def list_configs(ctx: click.Context, as_json: bool) -> None:
    """List the effective sandbox image configurations.

    Uses the Runtime API key. ``source`` is ``file`` for installer-managed
    entries and ``db`` for entries created through this command.
    """
    client = _client(ctx)
    configs = _run(client.list_configs)
    if as_json:
        _echo_json(configs)
    else:
        _echo_table(configs)


@images.command("get")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.pass_context
def get_config(ctx: click.Context, name: str, as_json: bool) -> None:
    """Show a single sandbox image configuration by NAME."""
    client = _client(ctx)
    config = _run(lambda: client.get_config(name))
    if config is None:
        raise click.ClickException(f'No configuration named "{name}".')
    if as_json:
        _echo_json(config)
    else:
        _echo_table([config])


@images.command("save")
@click.argument("name")
@click.option(
    "--file",
    "-f",
    "config_file",
    required=True,
    type=click.File("r"),
    help=(
        "JSON configuration body, or '-' for stdin. Derive it from the "
        "installer default (see 'ohe images save --help')."
    ),
)
@click.option("--image", help="Override the image reference in the config body.")
@click.option(
    "--count", type=int, help="Override the number of warm pods to keep ready."
)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.pass_context
def save_config(
    ctx: click.Context,
    name: str,
    config_file,
    image: str | None,
    count: int | None,
    as_json: bool,
) -> None:
    """Create or update the sandbox image configuration NAME (admin).

    The body must contain install-specific values (working_dir, command,
    environment) that sandboxes need to boot. Do not write it from scratch —
    export the installer default and change only the image and pool size:

    \b
      kubectl -n openhands get configmap warm-runtimes-config \\
        -o jsonpath='{.data.warm-runtimes\\.json}' \\
        | jq '.configs[] | select(.name == "v1_current") | del(.name)' \\
        > default-config.json

      ohe images save php-web -f default-config.json \\
        --image ghcr.io/your-org/openhands-php:8.4-v1 --count 1
    """
    try:
        body = json.load(config_file)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON in configuration file: {exc}") from exc
    if not isinstance(body, dict):
        raise click.ClickException("Configuration body must be a JSON object.")

    # A 'source' field appears in list output but must not be saved.
    body.pop("source", None)
    # The name is taken from the URL path, not the body.
    body.pop("name", None)
    if image is not None:
        body["image"] = image
    if count is not None:
        body["count"] = count

    missing = [f for f in _REQUIRED_FIELDS if not body.get(f)]
    if missing:
        raise click.ClickException(
            "Configuration is missing required field(s): "
            + ", ".join(missing)
            + ". Derive the body from the installer default template."
        )

    client = _client(ctx)
    saved = _run(lambda: client.save_config(name, body))
    if as_json:
        _echo_json(saved)
    else:
        click.echo(
            f"Saved {saved.get('name', name)}  "
            f"image={saved.get('image')}  count={saved.get('count')}"
        )


@images.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_context
def delete_config(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete the sandbox image configuration NAME (admin).

    If the deleted name also exists as an installer-managed entry, that entry
    becomes effective again on the next reconciler cycle.
    """
    if not yes and sys.stdin.isatty():
        click.confirm(f'Delete configuration "{name}"?', abort=True)
    client = _client(ctx)
    resp = _run(lambda: client.delete_config(name))
    click.echo(resp.get("message", f'Deleted "{name}".'))
