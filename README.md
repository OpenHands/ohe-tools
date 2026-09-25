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
# Point the CLI at your install's Runtime API and provide credentials.
export OHE_RUNTIME_API_URL=https://runtime-api.<your-base-domain>
export OHE_API_KEY=<runtime-api key>          # for read operations
export OHE_ADMIN_PASSWORD=<runtime-api admin> # for write operations

ohe images list
# Derive a new image from the installer default, changing only image + count:
ohe images save php-web --from v1_current \
  --image ghcr.io/your-org/openhands-php:8.4-v1 --count 1
ohe images delete php-web
```

## Command overview

```
ohe [--runtime-api-url URL] [--api-key KEY] [--admin-password PASSWORD] <command>

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

The Runtime API credential is **separate** from the standard OpenHands API
token. Values are resolved in this order:

| Setting | Option | Env (preferred) | Env (script-compatible) |
|---|---|---|---|
| Base URL | `--runtime-api-url` | `OHE_RUNTIME_API_URL` | `RUNTIME_API_URL` |
| API key (read) | `--api-key` | `OHE_API_KEY` | `API_KEY` |
| Admin password (write) | `--admin-password` | `OHE_ADMIN_PASSWORD` | `ADMIN_PASSWORD` |

Listing authenticates with the API key (`X-API-Key`). Saving and deleting use
the admin password via a PBKDF2 challenge-response login that returns a 24-hour
JWT; the client performs that handshake automatically.

On a cluster you can discover these values from Kubernetes secrets (this CLI is
a pure API client and deliberately does **not** shell out to `kubectl`):

```bash
NS=openhands
export OHE_RUNTIME_API_URL="https://$(kubectl get ingress -n "$NS" \
  -l app.kubernetes.io/name=runtime-api -o jsonpath='{.items[0].spec.rules[0].host}')"
export OHE_API_KEY="$(kubectl get secret default-api-key -n "$NS" \
  -o jsonpath='{.data.default-api-key}' | base64 -d)"
export OHE_ADMIN_PASSWORD="$(kubectl get secret admin-password -n "$NS" \
  -o jsonpath='{.data.admin-password}' | base64 -d)"
```

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
