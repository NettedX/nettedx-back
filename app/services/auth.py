"""实现 SIWE 认证的业务流程"""

from secrets import token_urlsafe
from time import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import OrganizationStatus
from app.db.models.organization import Organization
from app.db.models.siwe_nonce import SiweNonce
from app.schemas.auth import SiweChallengeData, SiweChallengeRequest
from app.schemas.exception import ServiceException


def _now_unix() -> int:
    return int(time())


def _normalize_wallet_address(wallet_address: str) -> str:
    return wallet_address.lower()


def _generate_nonce() -> str:
    return token_urlsafe(16)[:32]  # 生成一个16个字节的安全随机串，只保留前32个字符


def _build_siwe_message(
    wallet_address: str,
    chain_id: int,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> str:
    return (
        f"{settings.siwe_domain} wants you to sign in with your Ethereum account:\n"
        f"{wallet_address}\n\n"
        f"{settings.siwe_statement}\n\n"
        f"URI: {settings.siwe_uri}\n"
        "Version: 1\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}\n"
        f"Expiration Time: {expires_at}"
    )


# SIWE登录挑战业务实现
async def create_siwe_challenge(
    db: AsyncSession,
    payload: SiweChallengeRequest,
) -> SiweChallengeData:
    if payload.chain_id not in settings.allowed_siwe_chain_ids:
        raise ServiceException(status_code=400, detail="unsupported chain id")

    wallet_address = _normalize_wallet_address(payload.wallet_address)
    organization = await db.scalar(
        select(Organization).where(Organization.wallet_address == wallet_address)
    )

    if organization is None:
        raise ServiceException(status_code=400, detail="wallet address is not registered")

    if organization.status != OrganizationStatus.ENABLED:
        raise ServiceException(status_code=400, detail="organization is disabled")

    issued_at = _now_unix()
    expires_at = issued_at + settings.siwe_nonce_ttl_seconds
    nonce = _generate_nonce()

    db.add(
        SiweNonce(
            nonce=nonce,
            wallet_address=wallet_address,
            chain_id=payload.chain_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )
    await db.commit()

    return SiweChallengeData(
        message=_build_siwe_message(
            wallet_address=wallet_address,
            chain_id=payload.chain_id,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        ),
        expires_at=expires_at,
    )
