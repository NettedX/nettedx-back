"""实现 SIWE 认证的业务流程"""

import re
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_defunct

from secrets import token_urlsafe
from time import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import OrganizationStatus, UserStatus
from app.db.models.organization import Organization
from app.db.models.siwe_nonce import SiweNonce
from app.schemas.auth import SiweChallengeData, SiweChallengeRequest, SiweVerifyRequest, UserToken
from app.schemas.exception import ServiceException

from app.db.models.user import User
from app.schemas.auth import UserToken
from app.utils.auth import build_user_tokens


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


# 为指定钱包生成 SIWE 登录挑战，保存 nonce 并返回待签名消息。
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


# 解析后的 SIWE 消息结构体，用于统一保存域名、钱包地址、链 ID 和 nonce 等字段。
@dataclass(frozen=True)
class ParsedSiweMessage:
    domain: str
    wallet_address: str
    uri: str
    chain_id: int
    nonce: str
    expires_at: int


# 从 SIWE 文本中提取指定字段的值
def _extract_required_field(message: str, field_name: str) -> str:
    match = re.search(rf"^{re.escape(field_name)}: (.+)$", message, re.MULTILINE)
    if match is None:
        raise ServiceException(status_code=400, detail="invalid siwe message")
    return match.group(1).strip()


# 解析原始 SIWE 消息，校验格式并提取关键字段。
def _parse_siwe_message(message: str) -> ParsedSiweMessage:
    lines = message.splitlines()
    if len(lines) < 2:
        raise ServiceException(status_code=400, detail="invalid siwe message")

    domain_suffix = " wants you to sign in with your Ethereum account:"
    if not lines[0].endswith(domain_suffix):
        raise ServiceException(status_code=400, detail="invalid siwe message")

    domain = lines[0].removesuffix(domain_suffix)
    wallet_address = _normalize_wallet_address(lines[1].strip())

    try:
        chain_id = int(_extract_required_field(message, "Chain ID"))
        expires_at = int(_extract_required_field(message, "Expiration Time"))
    except ValueError as exc:
        raise ServiceException(status_code=400, detail="invalid siwe message") from exc

    return ParsedSiweMessage(
        domain=domain,
        wallet_address=wallet_address,
        uri=_extract_required_field(message, "URI"),
        chain_id=chain_id,
        nonce=_extract_required_field(message, "Nonce"),
        expires_at=expires_at,
    )


# 根据 SIWE 签名恢复签名钱包地址，用于校验签名是否由该地址发出。
def _recover_wallet_address(message: str, signature: str) -> str:
    try:
        signable_message = encode_defunct(text=message)
        return Account.recover_message(signable_message, signature=signature).lower()
    except Exception as exc:
        raise ServiceException(status_code=400, detail="invalid signature") from exc


async def verify_siwe_login(
    db: AsyncSession,
    payload: SiweVerifyRequest,
) -> UserToken:
    parsed = _parse_siwe_message(payload.message)

    if parsed.domain != settings.siwe_domain:
        raise ServiceException(status_code=400, detail="invalid siwe domain")

    if parsed.uri != settings.siwe_uri:
        raise ServiceException(status_code=400, detail="invalid siwe uri")

    if parsed.chain_id not in settings.allowed_siwe_chain_ids:
        raise ServiceException(status_code=400, detail="unsupported chain id")

    recovered_wallet_address = _recover_wallet_address(
        message=payload.message,
        signature=payload.signature,
    )
    if recovered_wallet_address != parsed.wallet_address:
        raise ServiceException(status_code=400, detail="signature wallet mismatch")

    now = _now_unix()
    nonce_record = await db.scalar(select(SiweNonce).where(SiweNonce.nonce == parsed.nonce))

    if nonce_record is None:
        raise ServiceException(status_code=400, detail="nonce not found")

    if nonce_record.used:
        raise ServiceException(status_code=400, detail="nonce already used")

    if nonce_record.expires_at < now:
        raise ServiceException(status_code=400, detail="nonce expired")

    if nonce_record.wallet_address != parsed.wallet_address:
        raise ServiceException(status_code=400, detail="nonce wallet mismatch")

    if nonce_record.chain_id != parsed.chain_id:
        raise ServiceException(status_code=400, detail="nonce chain mismatch")

    organization = await db.scalar(
        select(Organization).where(Organization.wallet_address == parsed.wallet_address)
    )
    if organization is None:
        raise ServiceException(status_code=400, detail="wallet address is not registered")

    if organization.status != OrganizationStatus.ENABLED:
        raise ServiceException(status_code=400, detail="organization is disabled")

    user = await db.scalar(
        select(User).where(
            User.organization_id == organization.id,
            User.status == UserStatus.ENABLED,
        )
    )
    if user is None:
        raise ServiceException(status_code=400, detail="user is not available")

    nonce_record.used = True
    nonce_record.used_at = now
    await db.commit()

    return build_user_tokens(uid=user.id)


async def refresh_user_tokens(
    db: AsyncSession,
    uid: int,
) -> UserToken:
    user = await db.scalar(select(User).where(User.id == uid))

    if user is None:
        raise ServiceException(status_code=401, detail="user not found")

    if user.status != UserStatus.ENABLED:
        raise ServiceException(status_code=401, detail="user is disabled")

    organization = await db.scalar(
        select(Organization).where(Organization.id == user.organization_id)
    )

    if organization is None:
        raise ServiceException(status_code=401, detail="organization not found")

    if organization.status != OrganizationStatus.ENABLED:
        raise ServiceException(status_code=401, detail="organization is disabled")

    return build_user_tokens(uid=user.id)
