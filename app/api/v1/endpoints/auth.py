"""认证接口：用于 SIWE 登录和 JWT 会话管理。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import SiweChallengeData, SiweChallengeRequest
from app.schemas.response import ApiResponse
from app.services.auth import create_siwe_challenge
from app.utils.response import build_success_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/siwe/nonce", response_model=ApiResponse[SiweChallengeData])
async def request_siwe_nonce(
    payload: SiweChallengeRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SiweChallengeData]:
    data = await create_siwe_challenge(db=db, payload=payload)
    return build_success_response(data=data)
