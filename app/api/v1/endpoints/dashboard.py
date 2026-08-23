"""提供登录后银行 Dashboard 的只读接口。"""

from fastapi import APIRouter

from app.api.dependencies.auth import AccessTokenPayload
from app.db.session import DbSession
from app.schemas.dashboard import (
    BankNetPositionItem,
    DashboardOverviewData,
    LiquidityShortfallItem,
    SettlementAssetRequirementItem,
    SettlementWindowForecastData,
)
from app.schemas.response import ApiResponse
from app.services.dashboard import (
    get_bank_liquidity_shortfalls,
    get_bank_net_positions,
    get_bank_settlement_asset_requirements,
    get_dashboard_overview,
    get_settlement_window_forecast,
)
from app.utils.response import build_success_response

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/settlement-window-forecast", response_model=ApiResponse[SettlementWindowForecastData])
async def read_settlement_window_forecast(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[SettlementWindowForecastData]:
    data = await get_settlement_window_forecast(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)


@router.get(
    "/net-positions",
    response_model=ApiResponse[list[BankNetPositionItem]],
    deprecated=True,
)
async def read_bank_net_positions(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[list[BankNetPositionItem]]:
    data = await get_bank_net_positions(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)


@router.get(
    "/settlement-asset-requirements",
    response_model=ApiResponse[list[SettlementAssetRequirementItem]],
    deprecated=True,
)
async def read_bank_settlement_asset_requirements(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[list[SettlementAssetRequirementItem]]:
    data = await get_bank_settlement_asset_requirements(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)


@router.get(
    "/liquidity-shortfalls",
    response_model=ApiResponse[list[LiquidityShortfallItem]],
    deprecated=True,
)
async def read_bank_liquidity_shortfalls(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[list[LiquidityShortfallItem]]:
    data = await get_bank_liquidity_shortfalls(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)


@router.get("/overview", response_model=ApiResponse[DashboardOverviewData])
async def read_dashboard_overview(
    token_payload: AccessTokenPayload,
    db: DbSession,
) -> ApiResponse[DashboardOverviewData]:
    data = await get_dashboard_overview(
        db=db,
        uid=token_payload["uid"],
    )
    return build_success_response(data=data)
