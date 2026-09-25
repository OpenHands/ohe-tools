"""A real in-process Runtime API stand-in for tests.

Implements the warm-runtime-config and admin-auth endpoints with the exact
request/response shapes and PBKDF2 challenge-response logic of the real
service, so tests exercise the client's real HTTP and auth code paths without
mocks.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from ohe.runtime_api.auth import compute_challenge_hash

ITERATIONS = 10000


class FakeRuntimeApiState:
    def __init__(self, *, api_key: str, admin_password: str | None) -> None:
        self.api_key = api_key
        self.admin_password = admin_password
        self.configs: dict[str, dict] = {}
        self._challenges: set[str] = set()
        self._tokens: set[str] = set()
        # Map of path -> number of remaining 503 responses to emit before 200.
        self.flaky: dict[str, int] = {}

    def new_challenge(self) -> dict:
        challenge = secrets.token_hex(16)
        salt = secrets.token_hex(16)
        self._challenges.add(challenge)
        return {"challenge": challenge, "salt": salt, "iterations": ITERATIONS}

    def issue_token(self) -> str:
        token = secrets.token_hex(16)
        self._tokens.add(token)
        return token

    def token_valid(self, token: str) -> bool:
        return token in self._tokens


def _make_handler(state: FakeRuntimeApiState):
    class Handler(BaseHTTPRequestHandler):
        # Track the last-issued salt per challenge for login verification.
        salts: ClassVar[dict[str, str]] = {}

        def log_message(self, *args):
            pass

        def _send(self, code: int, payload) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            return json.loads(raw) if raw else {}

        def _flaky_should_fail(self) -> bool:
            remaining = state.flaky.get(self.path, 0)
            if remaining > 0:
                state.flaky[self.path] = remaining - 1
                return True
            return False

        def do_GET(self):
            if self.path == "/api/admin/challenge":
                chal = state.new_challenge()
                Handler.salts[chal["challenge"]] = chal["salt"]
                self._send(200, chal)
                return
            if self.path == "/api/admin/api-keys":
                if not self._require_admin():
                    return
                self._send(
                    200,
                    [
                        {
                            "id": "key-1",
                            "name": "default",
                            "key_value": state.api_key,
                            "max_runtimes": None,
                            "remaining_credits": None,
                        }
                    ],
                )
                return
            if self.path == "/api/warm-runtime-configs":
                if self._flaky_should_fail():
                    self._send(503, {"detail": "temporarily unavailable"})
                    return
                if self.headers.get("X-API-Key") != state.api_key:
                    self._send(401, {"detail": "provide a valid API key"})
                    return
                self._send(200, {"configs": list(state.configs.values())})
                return
            self._send(404, {"detail": "not found"})

        def do_POST(self):
            if self.path == "/api/admin/login":
                if state.admin_password is None:
                    self._send(403, {"detail": "Admin functionality is disabled"})
                    return
                data = self._read_json()
                challenge = data.get("challenge", "")
                salt = Handler.salts.get(challenge)
                if salt is None:
                    self._send(400, {"detail": "Invalid or expired challenge"})
                    return
                expected = compute_challenge_hash(
                    state.admin_password, salt, challenge, ITERATIONS
                )
                if data.get("hash") != expected:
                    self._send(401, {"detail": "Invalid admin password"})
                    return
                self._send(200, {"token": state.issue_token()})
                return
            self._send(404, {"detail": "not found"})

        def _require_admin(self) -> bool:
            auth = self.headers.get("Authorization", "")
            token = auth[len("Bearer ") :] if auth.startswith("Bearer ") else ""
            if not state.token_valid(token):
                self._send(401, {"detail": "invalid token"})
                return False
            return True

        def _config_name(self) -> str:
            from urllib.parse import unquote

            return unquote(self.path.rsplit("/", 1)[-1])

        def do_PUT(self):
            if self.path.startswith("/api/admin/warm-runtime-configs/"):
                if not self._require_admin():
                    return
                name = self._config_name()
                body = self._read_json()
                item = {"name": name, "source": "db", **body}
                state.configs[name] = item
                self._send(200, item)
                return
            self._send(404, {"detail": "not found"})

        def do_DELETE(self):
            if self.path.startswith("/api/admin/warm-runtime-configs/"):
                if not self._require_admin():
                    return
                name = self._config_name()
                if name not in state.configs:
                    self._send(404, {"detail": f'Configuration "{name}" not found'})
                    return
                del state.configs[name]
                self._send(
                    200, {"message": f'Configuration "{name}" deleted successfully'}
                )
                return
            self._send(404, {"detail": "not found"})

    return Handler


@pytest.fixture
def fake_api():
    """Start a fake Runtime API and yield ``(base_url, state)``."""
    state = FakeRuntimeApiState(api_key="test-api-key", admin_password="s3cret")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
