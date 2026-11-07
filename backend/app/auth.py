"""Password and signed-token helpers for farmer authentication."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from . import config  # noqa: F401 - loads backend/.env before auth settings are read

_password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("SAFEAGRI_TOKEN_MINUTES", "720"))


def _secret() -> str:
    secret = os.getenv("SAFEAGRI_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "SAFEAGRI_SECRET_KEY is not configured. Set a long random secret before starting the API."
        )
    return secret


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def generate_node_key() -> str:
    """A fresh random credential for one sensor node. Shown to the farmer once."""
    return "sak_" + secrets.token_urlsafe(32)


def hash_node_key(key: str) -> str:
    # Node keys are 256 bits of randomness, so a fast hash is enough. Only the
    # hash is stored; a leaked database does not reveal usable keys.
    return hashlib.sha256(key.encode()).hexdigest()


_UNUSED_HASH = hash_node_key("no key issued")


def node_key_matches(provided: str | None, stored_hash: str | None) -> bool:
    """Constant-time check. Unknown nodes and unkeyed nodes run the same work."""
    candidate = hash_node_key(provided or "")
    same = secrets.compare_digest(candidate, stored_hash or _UNUSED_HASH)
    return same and stored_hash is not None and bool(provided)


def create_access_token(user_id: int, farm_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "farm_id": farm_id,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
