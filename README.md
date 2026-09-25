# ohe-tools

Command-line tools for operating **OpenHands Enterprise (OHE)**.

`ohe` is a small, dependency-light Python CLI with subcommands and good `--help`.
Its first capability is managing **custom sandbox images** (the Runtime API's
_warm runtime configurations_) — the same thing the documented
`warm-runtime-configs.sh` script does, but as a first-class command with proper
help, argument parsing, and clean error messages.

> License: [PolyForm Free Trial 1.0.0](./LICENSE) — the same license as
> `OpenHands/enterprise`.

## Install

```bash
pip install -e .        # from a checkout
ohe --help
```

Requires Python 3.10+. The only runtime dependency is `click`; everything else
is standard library.

## Quick start

```bash
# Supply your standard app URL and the admin password. The Runtime API URL is
# derived from the app URL (app.<domain> -> runtime-api.<domain>).
export OHE_APP_URL=https://app.<your-base-domain>
export OHE_ADMIN_PASSWORD=<Runtime API Admin Password>

ohe images list
# Derive a new image from the installer default, changing only image + count:
ohe images save php-web --from v1_current \
  --image ghcr.io/your-org/openhands-php:8.4-v1 --count 1
ohe images delete php-web
```

## Command overview

```
ohe [--app-url URL] [--admin-password PASSWORD] [--runtime-api-url URL] <command>

ohe images list                        List effective sandbox image configs
ohe images get   <name>                Show one configuration
ohe images save  <name> --from <src> [--image REF] [--count N]
                                       Derive from an existing config and save (admin)
ohe images save  <name> -f <config.json> [--image REF] [--count N]
                                       Save from a file / stdin (admin)
ohe images delete <name>               Delete a configuration (admin)
```

`ohe images list`/`get` accept `--json` for raw output; the default is a
compact table. `save` builds the body one of two ways — `--from <name>` fetches
an existing configuration from the API (typically the installer default,
`v1_current`) and strips its `name`/`source`, or `-f <file>` (`-` for stdin)
reads an edited body. Either way, `--image`/`--count` override in place. The
`--from` form collapses the docs' `list | jq | save` template dance into one
API-only command.

### Credentials

`ohe` is a pure API client — it never shells out to `kubectl`. You need two
things, both available without cluster access:

| Setting | Option | Env (preferred) | Env (compat) |
|---|---|---|---|
| App URL | `--app-url` | `OHE_APP_URL` | `APP_URL` |
| Admin password | `--admin-password` | `OHE_ADMIN_PASSWORD` | `ADMIN_PASSWORD` |
| Runtime API URL (override) | `--runtime-api-url` | `OHE_RUNTIME_API_URL` | `RUNTIME_API_URL` |
| API key (optional) | `--api-key` | `OHE_API_KEY` | `API_KEY` |

- **App URL** — your standard OpenHands URL, `https://app.<your-base-domain>`.
  The Runtime API URL is derived from it by swapping the first host label
  (`app` -> `runtime-api`), matching the installer's standard hostname layout.
  If you run a **custom** layout, set `--runtime-api-url` explicitly instead.
- **Admin password** — the **Runtime API Admin Password** from the installer.
  A random value is generated at install; set or reset your own in the
  **Admin Console → Config → Sandbox Configuration → Runtime API Admin
  Password**, then **Deploy**. This is the only credential you need to manage.

The admin password is sufficient for every `ohe images` operation. Writes
(`save`/`delete`) authenticate with it via a PBKDF2 challenge-response login
that returns a 24-hour JWT. Reads (`list`/`get`) need an `X-API-Key`; since the
Default API Key is hidden in the installer config, the client derives one from
the admin password automatically. Pass `--api-key` explicitly only if you
prefer to supply your own (it skips the derivation step).

The Runtime API credential is **separate** from the standard OpenHands API
token.

## Repository layout

```
ohe-tools/
├── LICENSE                       PolyForm Free Trial 1.0.0 (matches enterprise)
├── README.md
├── pyproject.toml                Packaging + `ohe` console-script entry point
├── src/ohe/
│   ├── cli.py                    Top-level `ohe` group, global options
│   ├── config.py                 Credential/URL resolution (options + env)
│   ├── commands/
│   │   └── images.py             `ohe images` subcommands
│   └── runtime_api/              Minimal Runtime API client (images only)
│       ├── auth.py               PBKDF2 challenge-response
│       ├── client.py             HTTP client + retries
│       └── errors.py             Typed exceptions
└── tests/                        Tests run against a real in-process HTTP server
```

The `runtime_api` package covers **only** the endpoints needed to manage
sandbox images. It is structured so additional OHE capabilities (for example
API-key administration) can be added as new `commands/` groups and client
methods without reworking the core.

## Sandbox image configuration format

`save` sends the JSON body straight to the Runtime API. Fields:

| Field | Required | Notes |
|---|---|---|
| `image` | yes | Full image reference |
| `working_dir` | yes | Copy from the installer default |
| `command` | yes | Agent-server start command — copy from the default |
| `environment` | yes | Install-specific env — copy from the default |
| `count` | no | Warm pods to keep ready |
| `run_as_user` / `run_as_group` / `fs_group` | no | Copy from the default |

Do not write configurations from scratch. Derive each image from the installer
default (`v1_current`) with `--from`, changing only the image and pool size —
`name` and `source` are stripped automatically. See the
[Configuring Custom Sandbox Images](https://docs.openhands.dev/enterprise) docs
for the full workflow, upgrade guidance, and troubleshooting.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
