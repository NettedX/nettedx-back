from types import SimpleNamespace
from typing import Any

import pytest
from hexbytes import HexBytes
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.auth import get_access_token_payload
from app.api.v1.endpoints import dashboard as dashboard_endpoints
from app.clients import blockchain as blockchain_client
from app.clients.blockchain import (
    RawBankNetPosition,
    RawDashboardAssetState,
    RawDashboardChainState,
    RawTradeEventChainStatus,
)
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.schemas.dashboard import AssetAmountObject, AssetTypeObject, DashboardOverviewData
from app.services import dashboard as dashboard_service

USDC_ADDRESS = "0x1111111111111111111111111111111111111111"
BOND_ADDRESS = "0x2222222222222222222222222222222222222222"
BANK_ADDRESS = "0x3333333333333333333333333333333333333333"
NETTING_ADDRESS = "0x4444444444444444444444444444444444444444"


class _FakeDb:
    async def rollback(self) -> None:
        return None


class _FakeContractCall:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def call(self) -> Any:
        return self.value


class _ChangingWindowFunctions:
    def __init__(self) -> None:
        self.window_ids = iter([0, 1, 1, 1])
        self.positions = iter(
            [
                [(USDC_ADDRESS, 500_000_000, 0)],
                [],
            ]
        )

    def currentWindowId(self) -> _FakeContractCall:
        return _FakeContractCall(next(self.window_ids))

    def getBankNetPositions(self, bank: str) -> _FakeContractCall:
        assert bank == BANK_ADDRESS
        return _FakeContractCall(next(self.positions))


def _overview_data(
    *,
    usdc_net_amount: int = -500_000_000,
    bond_net_amount: int = 5,
) -> DashboardOverviewData:
    usdc = AssetTypeObject(
        address=USDC_ADDRESS,
        name="Mock USDC",
        symbol="mUSDC",
        decimals=6,
        chain_id=31337,
    )
    bond = AssetTypeObject(
        address=BOND_ADDRESS,
        name="Mock Bond",
        symbol="mBOND",
        decimals=0,
        chain_id=31337,
    )
    return DashboardOverviewData(
        net_amounts=[
            AssetAmountObject(asset=usdc, amount=usdc_net_amount),
            AssetAmountObject(asset=bond, amount=bond_net_amount),
        ],
        cumulative_trade_count=12,
        liquidity_buffer_debts=[
            AssetAmountObject(asset=usdc, amount=400_000_000),
            AssetAmountObject(asset=bond, amount=0),
        ],
        cumulative_gross_trade_amounts=[
            AssetAmountObject(asset=usdc, amount=8_200_000_000),
            AssetAmountObject(asset=bond, amount=83),
        ],
        balances=[
            AssetAmountObject(asset=usdc, amount=1_250_000_000),
            AssetAmountObject(asset=bond, amount=21),
        ],
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("net_positions", "expected_net_amounts"),
    [
        (
            [
                RawBankNetPosition(
                    asset=USDC_ADDRESS,
                    payable_amount=500_000_000,
                    receivable_amount=0,
                ),
                RawBankNetPosition(
                    asset=BOND_ADDRESS,
                    payable_amount=0,
                    receivable_amount=5,
                ),
            ],
            (-500_000_000, 5),
        ),
        ([], (0, 0)),
    ],
    ids=["open-window", "settled-window"],
)
async def test_dashboard_overview_service_combines_chain_state_and_statistics(
    monkeypatch: pytest.MonkeyPatch,
    net_positions: list[RawBankNetPosition],
    expected_net_amounts: tuple[int, int],
) -> None:
    async def require_organization(*, db: Any, uid: int) -> Any:
        assert isinstance(db, _FakeDb)
        assert uid == 7
        return SimpleNamespace(wallet_address=BANK_ADDRESS)

    async def chain_state(bank: str) -> RawDashboardChainState:
        assert bank == BANK_ADDRESS
        return RawDashboardChainState(
            chain_id=31337,
            net_positions=net_positions,
            assets=[
                RawDashboardAssetState(
                    address=USDC_ADDRESS,
                    name="Mock USDC",
                    symbol="mUSDC",
                    decimals=6,
                    balance=1_250_000_000,
                    liquidity_buffer_debt=400_000_000,
                ),
                RawDashboardAssetState(
                    address=BOND_ADDRESS,
                    name="Mock Bond",
                    symbol="mBOND",
                    decimals=0,
                    balance=21,
                    liquidity_buffer_debt=0,
                ),
            ],
        )

    async def chain_status() -> RawTradeEventChainStatus:
        return RawTradeEventChainStatus(
            chain_id=31337,
            contract_address=NETTING_ADDRESS,
            latest_block=100,
        )

    async def sync_events(**_: Any) -> None:
        return None

    async def statistics(**_: Any) -> dashboard_service._TradeStatistics:
        return dashboard_service._TradeStatistics(
            count=12,
            cash_amount=8_200_000_000,
            bond_amount=83,
        )

    monkeypatch.setattr(dashboard_service, "_require_current_organization", require_organization)
    monkeypatch.setattr(dashboard_service, "fetch_dashboard_chain_state", chain_state)
    monkeypatch.setattr(dashboard_service, "fetch_trade_event_chain_status", chain_status)
    monkeypatch.setattr(dashboard_service, "_sync_trade_submitted_events", sync_events)
    monkeypatch.setattr(dashboard_service, "_get_trade_statistics", statistics)
    monkeypatch.setattr(settings, "mock_usdc_contract_address", USDC_ADDRESS)
    monkeypatch.setattr(settings, "mock_bond_contract_address", BOND_ADDRESS)

    result = await dashboard_service.get_dashboard_overview(db=_FakeDb(), uid=7)

    assert result.model_dump(by_alias=True) == _overview_data(
        usdc_net_amount=expected_net_amounts[0],
        bond_net_amount=expected_net_amounts[1],
    ).model_dump(by_alias=True)


@pytest.mark.anyio
async def test_dashboard_snapshot_reloads_net_amounts_after_settlement_window_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_reads = 0

    async def asset_state(**kwargs: Any) -> RawDashboardAssetState:
        nonlocal asset_reads
        asset_reads += 1
        return RawDashboardAssetState(
            address=kwargs["asset_address"],
            name="Mock Asset",
            symbol="MOCK",
            decimals=0,
            balance=0,
            liquidity_buffer_debt=0,
        )

    monkeypatch.setattr(blockchain_client, "_fetch_dashboard_asset_state", asset_state)
    netting = SimpleNamespace(functions=_ChangingWindowFunctions())

    positions, assets = await blockchain_client._fetch_consistent_dashboard_snapshot(
        netting=netting,
        liquidity_buffer=object(),
        tokens=[object(), object()],
        asset_addresses=[USDC_ADDRESS, BOND_ADDRESS],
        bank=BANK_ADDRESS,
    )

    assert positions == []
    assert len(assets) == 2
    assert asset_reads == 4


@pytest.mark.anyio
async def test_dashboard_overview_endpoint_uses_camel_case_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def db_override():
        yield object()

    async def overview(*, db: Any, uid: int) -> DashboardOverviewData:
        assert db is not None
        assert uid == 7
        return _overview_data()

    app.dependency_overrides[get_access_token_payload] = lambda: {"uid": 7}
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(dashboard_endpoints, "get_dashboard_overview", overview)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/dashboard/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"] == _overview_data().model_dump(mode="json", by_alias=True)


def test_dashboard_openapi_marks_legacy_endpoints_deprecated() -> None:
    paths = app.openapi()["paths"]

    assert paths["/v1/dashboard/net-positions"]["get"]["deprecated"] is True
    assert paths["/v1/dashboard/settlement-asset-requirements"]["get"]["deprecated"] is True
    assert paths["/v1/dashboard/liquidity-shortfalls"]["get"]["deprecated"] is True
    assert paths["/v1/dashboard/overview"]["get"].get("deprecated", False) is False


def test_trade_submitted_log_parser_preserves_full_event_data() -> None:
    events = blockchain_client._parse_trade_submitted_logs(
        [
            {
                "blockNumber": 20,
                "transactionHash": HexBytes(b"\x01" * 32),
                "logIndex": 3,
                "args": {
                    "windowId": 2,
                    "tradeId": 4,
                    "buyer": BANK_ADDRESS,
                    "seller": "0x5555555555555555555555555555555555555555",
                    "cashAmount": 500_000_000,
                    "bondAmount": 5,
                },
            }
        ]
    )

    assert len(events) == 1
    assert events[0].transaction_hash == f"0x{'01' * 32}"
    assert events[0].buyer == BANK_ADDRESS.lower()
    assert events[0].cash_amount == 500_000_000
    assert events[0].bond_amount == 5
