"""Password and signed-token helpers for farmer authentication."""
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

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
