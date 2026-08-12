"""认证接口：用于 SIWE 登录和 JWT 会话管理。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import SiweChallengeData, SiweChallengeRequest, UserProfile
from app.schemas.response import ApiResponse
from app.utils.response import build_success_response

from app.schemas.auth import (
    SiweChallengeData,
    SiweChallengeRequest,
    SiweVerifyRequest,
    UserToken,
)

from app.api.dependencies.auth import RefreshTokenPayload, AccessTokenPayload
from app.services.auth import (
    create_siwe_challenge,
    refresh_user_tokens,
    verify_siwe_login,
    get_user_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/siwe/nonce", response_model=ApiResponse[SiweChallengeData])
async def request_siwe_nonce(
    payload: SiweChallengeRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SiweChallengeData]:
    data = await create_siwe_challenge(db=db, payload=payload)
    return build_success_response(data=data)


@router.post("/siwe/verify", response_model=ApiResponse[UserToken])
async def verify_siwe_signature(
    payload: SiweVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserToken]:
    data = await verify_siwe_login(db=db, payload=payload)
    return build_success_response(data=data)


@router.get("/refresh", response_model=ApiResponse[UserToken])
async def refresh_token(
    token_payload: RefreshTokenPayload,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserToken]:
    data = await refresh_user_tokens(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)


@router.get("/profile", response_model=ApiResponse[UserProfile])
async def get_profile(
    token_payload: AccessTokenPayload,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserProfile]:
    data = await get_user_profile(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)
