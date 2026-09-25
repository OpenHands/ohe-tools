"""Exception types raised by the Runtime API client."""

from __future__ import annotations


class RuntimeApiError(Exception):
    """Base class for all Runtime API client errors."""


class AuthError(RuntimeApiError):
    """A required credential is missing or was rejected."""


class AdminDisabledError(AuthError):
    """The Runtime API has no admin password configured (HTTP 403)."""


class NotFoundError(RuntimeApiError):
    """The requested resource does not exist (HTTP 404)."""


class HttpError(RuntimeApiError):
    """An HTTP request returned a non-success status."""

    def __init__(self, status: int, body: str, url: str) -> None:
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} from {url}: {body}")
