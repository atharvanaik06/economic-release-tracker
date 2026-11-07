"""Memory-hard password hashing and opaque session-token helpers."""

import hashlib
import hmac
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a versioned scrypt password hash with an independent random salt."""
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=resolved_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    parameters = f"n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}"
    return f"scrypt${parameters}${resolved_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password while rejecting malformed or unsupported hashes safely."""
    try:
        algorithm, parameters, salt_hex, expected_hex = encoded_hash.split("$", maxsplit=3)
        parsed = dict(item.split("=", maxsplit=1) for item in parameters.split(","))
        if algorithm != "scrypt":
            return False
        n = int(parsed["n"])
        r = int(parsed["r"])
        p = int(parsed["p"])
        if (n, r, p) != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        if len(salt) != 16 or len(expected) != SCRYPT_DKLEN:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def new_session_token() -> str:
    """Create an unguessable token that is returned only to the browser."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Create the irreversible lookup value stored in PostgreSQL."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
