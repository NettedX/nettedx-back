"""处理首页公开分析数据的业务逻辑。"""

from app.clients.blockchain import (
    BlockchainClientError,
    fetch_public_analytics_metrics,
)
from app.core.config import settings
from app.schemas.exception import ServiceException
from app.schemas.public_analytics import PublicAnalyticsData


def _to_whole_cash_units(amount: int) -> int:
    """将现金代币最小单位转换为完整单位，并向下取整。"""

    return amount // (10**settings.cash_token_decimals)


async def get_public_analytics() -> PublicAnalyticsData:
    """读取并转换首页需要展示的四项公开指标。"""

    try:
        raw_metrics = await fetch_public_analytics_metrics()
    except BlockchainClientError as exc:
        # 不把 RPC 地址、API Key 或 Web3 底层异常暴露给接口调用方。
        raise ServiceException(
            status_code=503,
            detail="blockchain service unavailable",
        ) from exc

    if (
        raw_metrics.liquidity_saved > raw_metrics.total_settlement_amount
        or raw_metrics.obligation_reduction > 100
    ):
        raise ServiceException(
            status_code=503,
            detail="invalid blockchain analytics data",
        )

    return PublicAnalyticsData(
        total_settlement_amount=_to_whole_cash_units(raw_metrics.total_settlement_amount),
        total_trade_count=raw_metrics.total_trade_count,
        liquidity_saved=_to_whole_cash_units(raw_metrics.liquidity_saved),
        obligation_reduced=raw_metrics.obligation_reduction,
    )
