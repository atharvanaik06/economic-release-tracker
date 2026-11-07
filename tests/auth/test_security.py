"""Password and opaque-session security tests."""

from research_data_builder.auth import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)


def test_scrypt_password_hashes_are_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first.startswith("scrypt$n=16384,r=8,p=1$")
    assert first != second
    assert verify_password("correct horse battery staple", first) is True
    assert verify_password("incorrect", first) is False


def test_password_verification_rejects_malformed_or_unapproved_hashes() -> None:
    assert verify_password("anything", "not-a-password-hash") is False
    assert verify_password("anything", "argon2$n=16384,r=8,p=1$00$00") is False
    assert verify_password("anything", "scrypt$n=1,r=8,p=1$00$00") is False


def test_session_tokens_are_random_and_stored_as_fixed_hashes() -> None:
    first = new_session_token()
    second = new_session_token()

    assert first != second
    assert len(hash_session_token(first)) == 64
    assert hash_session_token(first) != first
    assert hash_session_token(first) != hash_session_token(second)
