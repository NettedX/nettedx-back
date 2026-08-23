"""处理登录后银行 Dashboard 的业务逻辑。"""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.blockchain import (
    BlockchainClientError,
    RawDashboardAssetState,
    RawTradeEventChainStatus,
    fetch_bank_liquidity_shortfalls,
    fetch_bank_net_positions,
    fetch_bank_settlement_asset_requirements,
    fetch_dashboard_chain_state,
    fetch_settlement_window_forecast,
    fetch_trade_event_chain_status,
    fetch_trade_submitted_events,
)
from app.core.config import settings
from app.db.enums import OrganizationStatus, UserStatus
from app.db.models.blockchain_event_cursor import BlockchainEventCursor
from app.db.models.organization import Organization
from app.db.models.trade_submitted_event import TradeSubmittedEvent
from app.db.models.user import User
from app.schemas.dashboard import (
    AssetAmountObject,
    AssetTypeObject,
    BankNetPositionItem,
    DashboardOverviewData,
    LiquidityShortfallItem,
    SettlementAssetRequirementItem,
    SettlementWindowForecastData,
)
from app.schemas.exception import ServiceException

ResultT = TypeVar("ResultT")
TRADE_SUBMITTED_EVENT_NAME = "TradeSubmitted"


@dataclass(frozen=True)
class _TradeStatistics:
    count: int
    cash_amount: int
    bond_amount: int


async def _require_current_organization(
    db: AsyncSession,
    uid: int,
) -> Organization:
    """取得当前用户所属的可用银行机构。"""

    user = await db.scalar(select(User).where(User.id == uid))

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
        select(Organization).where(Organization.id == user.organization_id)
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

    raw_forecast = await _read_blockchain_result(fetch_settlement_window_forecast())

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
        fetch_bank_settlement_asset_requirements(organization.wallet_address)
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
        fetch_bank_liquidity_shortfalls(organization.wallet_address)
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


async def get_dashboard_overview(
    db: AsyncSession,
    uid: int,
) -> DashboardOverviewData:
    """返回当前登录机构 Dashboard 所需的五项数据。"""

    organization = await _require_current_organization(db=db, uid=uid)

    try:
        chain_state, event_chain_status = await asyncio.gather(
            fetch_dashboard_chain_state(organization.wallet_address),
            fetch_trade_event_chain_status(),
        )
        if chain_state.chain_id != event_chain_status.chain_id:
            raise BlockchainClientError("inconsistent blockchain chain id")

        await _sync_trade_submitted_events(db=db, chain_status=event_chain_status)
    except BlockchainClientError as exc:
        await db.rollback()
        raise ServiceException(
            status_code=503,
            detail="blockchain service unavailable",
        ) from exc

    statistics = await _get_trade_statistics(
        db=db,
        chain_status=event_chain_status,
        wallet_address=organization.wallet_address,
    )

    net_amount_by_asset = {
        position.asset.lower(): position.receivable_amount - position.payable_amount
        for position in chain_state.net_positions
    }
    gross_amount_by_asset = {
        settings.mock_usdc_contract_address.lower(): statistics.cash_amount,
        settings.mock_bond_contract_address.lower(): statistics.bond_amount,
    }

    return DashboardOverviewData(
        net_amounts=[
            _asset_amount(
                asset=asset,
                chain_id=chain_state.chain_id,
                amount=net_amount_by_asset.get(asset.address.lower(), 0),
            )
            for asset in chain_state.assets
        ],
        cumulative_trade_count=statistics.count,
        liquidity_buffer_debts=[
            _asset_amount(
                asset=asset,
                chain_id=chain_state.chain_id,
                amount=asset.liquidity_buffer_debt,
            )
            for asset in chain_state.assets
        ],
        cumulative_gross_trade_amounts=[
            _asset_amount(
                asset=asset,
                chain_id=chain_state.chain_id,
                amount=gross_amount_by_asset.get(asset.address.lower(), 0),
            )
            for asset in chain_state.assets
        ],
        balances=[
            _asset_amount(
                asset=asset,
                chain_id=chain_state.chain_id,
                amount=asset.balance,
            )
            for asset in chain_state.assets
        ],
    )


def _asset_amount(
    *,
    asset: RawDashboardAssetState,
    chain_id: int,
    amount: int,
) -> AssetAmountObject:
    """将链上资产状态转换为公共 AssetAmountObject。"""

    return AssetAmountObject(
        asset=AssetTypeObject(
            address=asset.address,
            name=asset.name,
            symbol=asset.symbol,
            decimals=asset.decimals,
            chain_id=chain_id,
        ),
        amount=amount,
    )


async def _sync_trade_submitted_events(
    *,
    db: AsyncSession,
    chain_status: RawTradeEventChainStatus,
) -> None:
    """从数据库游标开始增量同步 TradeSubmitted 日志。"""

    target_block = max(
        settings.netting_deployment_block - 1,
        chain_status.latest_block - settings.blockchain_event_confirmations,
    )
    cursor = await db.scalar(
        select(BlockchainEventCursor)
        .where(
            BlockchainEventCursor.chain_id == chain_status.chain_id,
            BlockchainEventCursor.contract_address == chain_status.contract_address,
            BlockchainEventCursor.event_name == TRADE_SUBMITTED_EVENT_NAME,
        )
        .with_for_update()
    )

    if cursor is None:
        cursor = BlockchainEventCursor(
            chain_id=chain_status.chain_id,
            contract_address=chain_status.contract_address,
            event_name=TRADE_SUBMITTED_EVENT_NAME,
            last_synced_block=settings.netting_deployment_block - 1,
        )
        db.add(cursor)
        await db.flush()
    elif cursor.last_synced_block > target_block:
        # 本地 Anvil 等开发链重启后区块高度可能回退；清空旧链事件重新索引。
        await db.execute(
            delete(TradeSubmittedEvent).where(
                TradeSubmittedEvent.chain_id == chain_status.chain_id,
                TradeSubmittedEvent.contract_address == chain_status.contract_address,
            )
        )
        cursor.last_synced_block = settings.netting_deployment_block - 1

    next_block = max(cursor.last_synced_block + 1, settings.netting_deployment_block)
    while next_block <= target_block:
        chunk_end = min(
            next_block + settings.blockchain_event_scan_chunk_size - 1,
            target_block,
        )
        events = await fetch_trade_submitted_events(next_block, chunk_end)
        for event in events:
            existing_id = await db.scalar(
                select(TradeSubmittedEvent.id).where(
                    TradeSubmittedEvent.chain_id == chain_status.chain_id,
                    TradeSubmittedEvent.contract_address == chain_status.contract_address,
                    TradeSubmittedEvent.transaction_hash == event.transaction_hash,
                    TradeSubmittedEvent.log_index == event.log_index,
                )
            )
            if existing_id is not None:
                continue

            db.add(
                TradeSubmittedEvent(
                    chain_id=chain_status.chain_id,
                    contract_address=chain_status.contract_address,
                    block_number=event.block_number,
                    transaction_hash=event.transaction_hash,
                    log_index=event.log_index,
                    window_id=str(event.window_id),
                    trade_id=str(event.trade_id),
                    buyer=event.buyer,
                    seller=event.seller,
                    cash_amount=str(event.cash_amount),
                    bond_amount=str(event.bond_amount),
                )
            )

        cursor.last_synced_block = chunk_end
        await db.flush()
        next_block = chunk_end + 1

    await db.commit()


async def _get_trade_statistics(
    *,
    db: AsyncSession,
    chain_status: RawTradeEventChainStatus,
    wallet_address: str,
) -> _TradeStatistics:
    """从已索引事件计算钱包累计次数及两种资产的原始绝对金额。"""

    normalized_wallet = wallet_address.lower()
    result = await db.execute(
        select(
            TradeSubmittedEvent.cash_amount,
            TradeSubmittedEvent.bond_amount,
        ).where(
            TradeSubmittedEvent.chain_id == chain_status.chain_id,
            TradeSubmittedEvent.contract_address == chain_status.contract_address,
            or_(
                TradeSubmittedEvent.buyer == normalized_wallet,
                TradeSubmittedEvent.seller == normalized_wallet,
            ),
        )
    )
    rows = result.all()

    return _TradeStatistics(
        count=len(rows),
        cash_amount=sum(int(row.cash_amount) for row in rows),
        bond_amount=sum(int(row.bond_amount) for row in rows),
    )
