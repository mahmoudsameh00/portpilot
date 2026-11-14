"""Password hashing for the API's logins (FastAPI plan §6, owner A1): stdlib `hashlib.scrypt`, no new package.

Stored form (`api.logins.password_hash`): `scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>` — the parameters travel with the
hash, so they can be raised later without breaking existing logins. Parameters = OWASP's scrypt minimum (N = 2^17,
r = 8, p = 1: 128 MiB, ≈ 2.1 s per hash measured on the i7-9750H, 2026-11-03 — sign-ins are rare, guessing is what it
slows; the API runs it in a worker thread, never on the event loop).
"""
import base64
import hashlib
import hmac
import secrets

N, R, P = 2 ** 17, 8, 1
SALT_BYTES, KEY_BYTES = 16, 32
MAXMEM = 2 ** 28                     # hashlib's default (32 MiB) is below 128 · r · N
MIN_LENGTH = 12


def _key(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=MAXMEM, dklen=KEY_BYTES)


def hash_password(password: str) -> str:
    if len(password) < MIN_LENGTH:
        raise ValueError(f"a password needs at least {MIN_LENGTH} characters")
    salt = secrets.token_bytes(SALT_BYTES)
    b64 = base64.b64encode
    return f"scrypt${N}${R}${P}${b64(salt).decode()}${b64(_key(password, salt, N, R, P)).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """True when `password` matches `stored`; False for a wrong password or a malformed hash (never raises)."""
    try:
        kind, n, r, p, salt, key = stored.split("$")
        if kind != "scrypt":
            return False
        expected = base64.b64decode(key, validate=True)
        got = _key(password, base64.b64decode(salt, validate=True), int(n), int(r), int(p))
    except ValueError:                # wrong shape, bad base64, bad parameters
        return False
    return hmac.compare_digest(got, expected)
