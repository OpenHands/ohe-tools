import hashlib

from ohe.runtime_api.auth import compute_challenge_hash


def test_hash_matches_server_derivation():
    # Mirror the server: PBKDF2-HMAC-SHA256 over (salt + challenge) as UTF-8.
    password, salt, challenge, iterations = "s3cret", "abc123", "deadbeef", 10000
    expected = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        (salt + challenge).encode("utf-8"),
        iterations,
        dklen=32,
    ).hex()
    assert compute_challenge_hash(password, salt, challenge, iterations) == expected


def test_hash_is_sensitive_to_inputs():
    base = compute_challenge_hash("pw", "salt", "chal", 10000)
    assert compute_challenge_hash("PW", "salt", "chal", 10000) != base
    assert compute_challenge_hash("pw", "SALT", "chal", 10000) != base
    assert compute_challenge_hash("pw", "salt", "CHAL", 10000) != base


def test_salt_and_challenge_not_interchangeable():
    # Concatenation order must match the server; swapping changes the digest.
    assert compute_challenge_hash("pw", "AB", "CD", 10000) != compute_challenge_hash(
        "pw", "CD", "AB", 10000
    )
