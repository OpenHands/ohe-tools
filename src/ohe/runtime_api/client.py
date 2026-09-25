"""HTTP client for the subset of the Runtime API that manages sandbox images.

Only warm-runtime-config endpoints and the admin auth flow are implemented:

* ``GET  /api/warm-runtime-configs``               (X-API-Key)
* ``PUT  /api/admin/warm-runtime-configs/{name}``  (admin JWT)
* ``DELETE /api/admin/warm-runtime-configs/{name}``(admin JWT)
* ``GET  /api/admin/challenge`` / ``POST /api/admin/login`` (admin auth)

The implementation uses only the standard library so the tool has a single
third-party dependency (click) and stays easy to vendor into a cluster.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ohe.runtime_api.auth import compute_challenge_hash
from ohe.runtime_api.errors import (
    AdminDisabledError,
    AuthError,
    HttpError,
    NotFoundError,
    RuntimeApiError,
)

# Transient statuses worth retrying with backoff.
_RETRY_STATUSES = frozenset({429, 502, 503, 504})


class RuntimeApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        admin_password: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        base_backoff: float = 1.0,
        opener: urllib.request.OpenerDirector | None = None,
        sleep=time.sleep,
    ) -> None:
        if not base_url:
            raise RuntimeApiError("A Runtime API base URL is required.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.admin_password = admin_password
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._opener = opener or urllib.request.build_opener()
        self._sleep = sleep
        self._admin_token: str | None = None
        self._resolved_api_key: str | None = None

    # -- low-level request ------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req_headers = {"Accept": "application/json"}
        if body is not None:
            req_headers["Content-Type"] = "application/json"
        if headers:
            req_headers.update(headers)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(
                url, data=body, headers=req_headers, method=method
            )
            try:
                with self._opener.open(request, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                detail = _read_error_body(exc)
                if exc.code in _RETRY_STATUSES and attempt < self.max_retries:
                    self._sleep(self._retry_delay(attempt, exc.headers))
                    last_error = exc
                    continue
                raise _translate_http_error(exc.code, detail, url) from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    self._sleep(self._retry_delay(attempt, None))
                    last_error = exc
                    continue
                raise RuntimeApiError(
                    f"Could not connect to {url}: {exc.reason}"
                ) from exc

        # Exhausted retries on a transient failure.
        raise RuntimeApiError(f"Request to {url} failed after retries: {last_error}")

    def _retry_delay(self, attempt: int, resp_headers) -> float:
        retry_after = resp_headers.get("Retry-After") if resp_headers else None
        if retry_after:
            try:
                return float(retry_after) + 0.5
            except ValueError:
                pass
        return self.base_backoff * (2**attempt) + random.uniform(0.0, 1.0)

    # -- auth -------------------------------------------------------------

    def _api_key_headers(self) -> dict:
        return {"X-API-Key": self._resolve_api_key()}

    def _resolve_api_key(self) -> str:
        """Return an API key for read calls.

        Uses an explicitly provided key, otherwise derives one from the admin
        password via the admin api-keys endpoint. The Default API Key is hidden
        in the Replicated installer config, so deriving it from the admin
        password (which the installer *does* expose) keeps read operations
        working without any cluster access.
        """
        if self.api_key:
            return self.api_key
        if self._resolved_api_key:
            return self._resolved_api_key
        if self.admin_password:
            keys = self.get_api_keys()
            key_value = next(
                (k.get("key_value") for k in keys if k.get("key_value")), None
            )
            if not key_value:
                raise AuthError(
                    "No API key is available to derive from the admin account."
                )
            self._resolved_api_key = key_value
            return key_value
        raise AuthError(
            "No credentials for this operation. Provide --admin-password "
            "(the Runtime API Admin Password from the installer config), or "
            "an explicit --api-key."
        )

    def get_api_keys(self) -> list[dict]:
        """Return all Runtime API keys (admin only)."""
        return self._request(
            "GET", "/api/admin/api-keys", headers=self._admin_headers()
        )

    def admin_token(self, *, refresh: bool = False) -> str:
        """Log in with the admin password and return a bearer JWT (cached)."""
        if self._admin_token is not None and not refresh:
            return self._admin_token
        if not self.admin_password:
            raise AuthError(
                "An admin password is required for this operation. "
                "Set --admin-password or the OHE_ADMIN_PASSWORD environment "
                "variable."
            )
        challenge = self._request("GET", "/api/admin/challenge")
        hashed = compute_challenge_hash(
            self.admin_password,
            challenge["salt"],
            challenge["challenge"],
            challenge["iterations"],
        )
        resp = self._request(
            "POST",
            "/api/admin/login",
            data={"challenge": challenge["challenge"], "hash": hashed},
        )
        self._admin_token = resp["token"]
        return self._admin_token

    def _admin_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.admin_token()}"}

    # -- warm runtime configs (sandbox images) ---------------------------

    def list_configs(self) -> list[dict]:
        """Return the effective set of warm runtime configurations."""
        resp = self._request(
            "GET", "/api/warm-runtime-configs", headers=self._api_key_headers()
        )
        return resp["configs"]

    def get_config(self, name: str) -> dict | None:
        """Return a single configuration by name, or ``None`` if absent."""
        for config in self.list_configs():
            if config.get("name") == name:
                return config
        return None

    def save_config(self, name: str, body: dict) -> dict:
        """Create or overwrite the configuration named ``name`` (admin)."""
        quoted = urllib.parse.quote(name, safe="")
        return self._request(
            "PUT",
            f"/api/admin/warm-runtime-configs/{quoted}",
            data=body,
            headers=self._admin_headers(),
        )

    def delete_config(self, name: str) -> dict:
        """Delete the database-backed configuration named ``name`` (admin)."""
        quoted = urllib.parse.quote(name, safe="")
        return self._request(
            "DELETE",
            f"/api/admin/warm-runtime-configs/{quoted}",
            headers=self._admin_headers(),
        )


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
    except Exception:  # noqa: BLE001 - best-effort error detail
        return ""
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if isinstance(parsed, dict) and "detail" in parsed:
        return str(parsed["detail"])
    return raw


def _translate_http_error(status: int, detail: str, url: str) -> RuntimeApiError:
    if status == 403 and "admin" in detail.lower():
        return AdminDisabledError(detail or "Admin functionality is disabled.")
    if status in (401, 403):
        return AuthError(detail or f"HTTP {status}: authentication failed.")
    if status == 404:
        return NotFoundError(detail or f"HTTP 404: not found ({url}).")
    return HttpError(status, detail, url)
