"""提供 FastAPI 路由使用的 JWT Bearer 鉴权依赖。
Access Token 和 Refresh Token 使用相同的 Authorization Bearer
请求格式，但根据 JWT Payload 中的 typ 字段限制具体用途。
"""

from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.exception import ServiceException
from app.utils.auth import decode_user_token

http_bearer = HTTPBearer(auto_error=False)

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(http_bearer),
]


# 从Bearer凭证中取得token；请求未携带凭证时抛出业务异常.
def _require_token(credentials: BearerCredentials) -> str:
    if credentials is None:
        raise ServiceException(
            status_code=401,
            detail="missing authorization",
        )

    return credentials.credentials


# 验证 Access Token 并返回 JWT Payload。
def get_access_token_payload(
    credentials: BearerCredentials,
) -> dict[str, Any]:
    token = _require_token(credentials)
    return decode_user_token(
        token,
        expected_types={"access"},
    )


# 验证 Refresh Token 并返回 JWT Payload。
def get_refresh_token_payload(
    credentials: BearerCredentials,
) -> dict[str, Any]:
    token = _require_token(credentials)
    return decode_user_token(
        token,
        expected_types={"refresh"},
    )


AccessTokenPayload = Annotated[
    dict[str, Any],
    Depends(get_access_token_payload),
]

RefreshTokenPayload = Annotated[
    dict[str, Any],
    Depends(get_refresh_token_payload),
]
