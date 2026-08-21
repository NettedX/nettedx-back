"""处理登录后银行 Dashboard 的业务逻辑。"""

from collections.abc import Awaitable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.blockchain import (
    BlockchainClientError,
    fetch_bank_liquidity_shortfalls,
    fetch_bank_net_positions,
    fetch_bank_settlement_asset_requirements,
    fetch_settlement_window_forecast,
)
from app.db.enums import OrganizationStatus, UserStatus
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.dashboard import (
    BankNetPositionItem,
    LiquidityShortfallItem,
    SettlementAssetRequirementItem,
    SettlementWindowForecastData,
)
from app.schemas.exception import ServiceException

ResultT = TypeVar("ResultT")


async def _require_current_organization(
    db: AsyncSession,
    uid: int,
) -> Organization:
    """取得当前用户所属的可用银行机构。"""

    user = await db.scalar(
        select(User).where(User.id == uid)
    )

    if user is None:
        raise ServiceException(
            status_code=401,
            detail="user not found",
        )

    if user.status != UserStatus.ENABLED:
        raise ServiceException(
            status_code=401,
            detail="user is disabled",
        )

    organization = await db.scalar(
        select(Organization).where(
            Organization.id == user.organization_id
        )
    )

    if organization is None:
        raise ServiceException(
            status_code=401,
            detail="organization not found",
        )

    if organization.status != OrganizationStatus.ENABLED:
        raise ServiceException(
            status_code=401,
            detail="organization is disabled",
        )

    return organization


async def _read_blockchain_result(
    operation: Awaitable[ResultT],
) -> ResultT:
    """调用链上读取操作，并统一隐藏底层 Web3 异常。"""

    try:
        return await operation
    except BlockchainClientError as exc:
        raise ServiceException(
            status_code=503,
            detail="blockchain service unavailable",
        ) from exc


async def get_settlement_window_forecast(
    db: AsyncSession,
    uid: int,
) -> SettlementWindowForecastData:
    """返回当前登录用户可查看的结算窗口预测。"""

    await _require_current_organization(db=db, uid=uid)

    raw_forecast = await _read_blockchain_result(
        fetch_settlement_window_forecast()
    )

    return SettlementWindowForecastData(
        window_id=raw_forecast.window_id,
        settlement_block=raw_forecast.settlement_block,
        blocks_remaining=raw_forecast.blocks_remaining,
    )


async def get_bank_net_positions(
    db: AsyncSession,
    uid: int,
) -> list[BankNetPositionItem]:
    """返回当前银行按金融产品区分的应付和应收头寸。"""

    organization = await _require_current_organization(
        db=db,
        uid=uid,
    )
    raw_positions = await _read_blockchain_result(
        fetch_bank_net_positions(organization.wallet_address)
    )

    return [
        BankNetPositionItem(
            asset=item.asset,
            payable_amount=item.payable_amount,
            receivable_amount=item.receivable_amount,
        )
        for item in raw_positions
    ]


async def get_bank_settlement_asset_requirements(
    db: AsyncSession,
    uid: int,
) -> list[SettlementAssetRequirementItem]:
    """返回当前银行本轮必须准备的金融产品及数量。"""

    organization = await _require_current_organization(
        db=db,
        uid=uid,
    )
    raw_requirements = await _read_blockchain_result(
        fetch_bank_settlement_asset_requirements(
            organization.wallet_address
        )
    )

    return [
        SettlementAssetRequirementItem(
            asset=item.asset,
            required_amount=item.required_amount,
        )
        for item in raw_requirements
    ]


async def get_bank_liquidity_shortfalls(
    db: AsyncSession,
    uid: int,
) -> list[LiquidityShortfallItem]:
    """返回当前银行的结算流动性缺口。"""

    organization = await _require_current_organization(
        db=db,
        uid=uid,
    )
    raw_shortfalls = await _read_blockchain_result(
        fetch_bank_liquidity_shortfalls(
            organization.wallet_address
        )
    )

    return [
        LiquidityShortfallItem(
            asset=item.asset,
            required_amount=item.required_amount,
            available_balance=item.available_balance,
            borrow_amount=item.borrow_amount,
        )
        for item in raw_shortfalls
    ]