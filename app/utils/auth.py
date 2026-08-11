"""提供给用户JWT的签发和验证功能。"""

from typing import Any, Literal
from time import time

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings
from app.schemas.auth import UserToken
from app.schemas.exception import ServiceException

TokenType = Literal["access", "refresh"]


# 签发指定类型和有效时间的JWT
def _build_token(
    uid: int,
    token_type: TokenType,
    ttl_seconds: int,
) -> str:
    now = int(time())
    payload = {
        "sub": str(uid),
        "uid": uid,
        "typ": token_type,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


# 为用户同时签发Access token和Refresh token
def build_user_tokens(uid: int) -> UserToken:
    access = _build_token(
        uid=uid,
        token_type="access",
        ttl_seconds=settings.jwt_access_ttl_seconds,
    )
    refresh = _build_token(
        uid=uid,
        token_type="refresh",
        ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )

    return UserToken(
        access=access,
        refresh=refresh,
    )


# 验证JWT并返回payload
def decode_user_token(
    token: str,
    expected_types: set[TokenType] | None = None,
) -> dict[str, Any]:  # expected_types用于限制当前api允许的token类型
    try:
        payload = jwt.decode(  # payload被修改后签名验证会失败
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": [
                    "sub",
                    "uid",
                    "typ",
                    "iat",
                    "exp",  # PyJWT 自动检查是否过期
                ]
            },
        )
    except ExpiredSignatureError as exc:
        raise ServiceException(
            status_code=401,
            detail="token expired",
        ) from exc
    except InvalidTokenError as exc:
        raise ServiceException(
            status_code=401,
            detail="invalid token",
        ) from exc

    uid = payload.get("uid")
    token_type = payload.get("typ")

    if not isinstance(uid, int):
        raise ServiceException(
            status_code=401,
            detail="invalid token payload",
        )

    if token_type not in {"access", "refresh"}:
        raise ServiceException(
            status_code=401,
            detail="invalid token type",
        )

    if expected_types is not None and token_type not in expected_types:
        raise ServiceException(
            status_code=401,
            detail="invalid token type",
        )

    return payload
