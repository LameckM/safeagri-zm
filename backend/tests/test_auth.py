import pytest

from app import auth


def test_password_hash_verifies_without_storing_plaintext():
    hashed = auth.hash_password("Correct-Horse-42!")
    assert hashed != "Correct-Horse-42!"
    assert auth.verify_password("Correct-Horse-42!", hashed)
    assert not auth.verify_password("wrong-password", hashed)


def test_access_token_contains_user_and_farm_claims(monkeypatch):
    monkeypatch.setenv("SAFEAGRI_SECRET_KEY", "test-only-secret-key-with-enough-randomness")
    token = auth.create_access_token(user_id=7, farm_id=3)
    payload = auth.decode_access_token(token)
    assert payload["sub"] == "7"
    assert payload["farm_id"] == 3


def test_token_creation_requires_configured_secret(monkeypatch):
    monkeypatch.delenv("SAFEAGRI_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SAFEAGRI_SECRET_KEY"):
        auth.create_access_token(user_id=1, farm_id=1)


def test_node_key_helpers_hash_and_compare():
    key = auth.generate_node_key()
    assert key.startswith("sak_") and len(key) > 40
    assert key != auth.generate_node_key()
    stored = auth.hash_node_key(key)
    assert stored != key
    assert auth.node_key_matches(key, stored)
    assert not auth.node_key_matches("sak_other", stored)
    assert not auth.node_key_matches(None, stored)
    assert not auth.node_key_matches("", stored)
    assert not auth.node_key_matches(key, None)  # node has no key issued
