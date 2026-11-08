"""Sensor-node credential helpers. The dashboard itself has no account login."""
import hashlib
import secrets

_UNUSED_HASH = hashlib.sha256(b"no key issued").hexdigest()


def generate_node_key() -> str:
    return "sak_" + secrets.token_urlsafe(32)


def hash_node_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def node_key_matches(provided: str | None, stored_hash: str | None) -> bool:
    candidate = hash_node_key(provided or "")
    same = secrets.compare_digest(candidate, stored_hash or _UNUSED_HASH)
    return same and stored_hash is not None and bool(provided)
