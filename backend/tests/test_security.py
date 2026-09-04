from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("Clave-Muy-Segura-123!")
    assert hashed != "Clave-Muy-Segura-123!"
    assert verify_password("Clave-Muy-Segura-123!", hashed)
    assert not verify_password("otra-clave", hashed)


def test_jwt_roundtrip():
    token = create_access_token("11111111-1111-1111-1111-111111111111")
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["type"] == "access"
