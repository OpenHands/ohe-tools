"""Admin challenge-response authentication for the Runtime API.

The Runtime API admin endpoints use a PBKDF2 challenge-response login rather
than sending the password directly. The server returns a one-time ``challenge``
and ``salt``; the client derives a key with
``PBKDF2-HMAC-SHA256(password, salt + challenge)`` and posts back the hex digest
to exchange it for a short-lived JWT.

The derivation here mirrors the server exactly (``management_fastapi.py`` in
OpenHands/runtime-api): salt and challenge are concatenated as UTF-8 strings —
not decoded from hex — before hashing.
"""

from __future__ import annotations

import binascii
import hashlib

DEFAULT_DKLEN = 32


def compute_challenge_hash(
    password: str,
    salt: str,
    challenge: str,
    iterations: int,
    dklen: int = DEFAULT_DKLEN,
) -> str:
    """Return the hex-encoded PBKDF2 hash the ``/admin/login`` endpoint expects."""
    combined_salt = (salt + challenge).encode("utf-8")
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        combined_salt,
        iterations,
        dklen=dklen,
    )
    return binascii.hexlify(dk).decode("ascii")
