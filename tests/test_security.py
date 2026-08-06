from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_round_trip() -> None:
    hashed = hash_password("A-strong-password-123")
    assert verify_password("A-strong-password-123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip() -> None:
    token = create_access_token("00000000-0000-0000-0000-000000000001")
    assert decode_access_token(token) == "00000000-0000-0000-0000-000000000001"
