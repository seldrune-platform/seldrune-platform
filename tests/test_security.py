from uuid import uuid4

import jwt

from backend.app.core.config import settings
from backend.app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    stored_hash = hash_password("correct horse battery staple")
    assert stored_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", stored_hash)
    assert not verify_password("wrong password", stored_hash)


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_access_token_rejects_wrong_secret() -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": 1, "exp": 4102444800},
        "not-the-seldrune-secret",
        algorithm="HS256",
    )

    try:
        decode_access_token(token)
    except TokenError:
        pass
    else:
        raise AssertionError("Token signed with the wrong secret was accepted")


def test_development_secret_is_not_blank() -> None:
    assert settings.auth_secret_key
