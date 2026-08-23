from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.dependencies.auth import get_access_token_payload
from app.api.v1.endpoints import transactions as transaction_endpoints
from app.db.enums import TransactionStatus
from app.db.session import get_db
from app.main import app
from app.schemas.transactions import (
    AssetAmountObject,
    AssetTypeObject,
    CreateTransactionRequest,
    OrganizationSummary,
    TransactionDetail,
)

HASH = f"0x{'12' * 32}"


def _detail() -> TransactionDetail:
    sender = OrganizationSummary(id=1, code="BANK_A", name="Bank A")
    receiver = OrganizationSummary(id=2, code="BANK_B", name="Bank B")
    usdc = AssetTypeObject(
        address=f"0x{'11' * 20}",
        name="Mock USDC",
        symbol="mUSDC",
        decimals=6,
        chain_id=31337,
    )
    bond = AssetTypeObject(
        address=f"0x{'22' * 20}",
        name="Mock Bond",
        symbol="mBOND",
        decimals=0,
        chain_id=31337,
    )
    return TransactionDetail(
        id=101,
        created_by=sender,
        sender_organization=sender,
        send=AssetAmountObject(asset=usdc, amount=500_000_000),
        receiver_organization=receiver,
        receive=AssetAmountObject(asset=bond, amount=5),
        status=TransactionStatus.SUBMITTED,
        chain_id=31337,
        window_id=0,
        submission_hash=HASH,
        created_at=1_780_000_000,
    )


@pytest.fixture
def api_dependencies() -> None:
    async def override_db() -> Any:
        yield SimpleNamespace()

    def override_access_token() -> dict[str, int]:
        return {"uid": 1}

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_access_token_payload] = override_access_token
    yield
    app.dependency_overrides.clear()


def test_create_request_rejects_same_asset_pair() -> None:
    with pytest.raises(ValidationError):
        CreateTransactionRequest.model_validate(
            {
                "receiverOrganizationId": 2,
                "send": {"asset": "USDC", "amount": 1},
                "receive": {"asset": "USDC", "amount": 1},
            }
        )


def test_transaction_openapi_matches_frontend_paths_and_fields() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert "/v1/transactions/send" in paths
    assert "/v1/transactions" in paths
    assert "/v1/transactions/verify" in paths
    assert "/v1/transactions/organizations" in paths
    assert "/v1/transactions/{transactionId}" in paths

    detail_fields = schema["components"]["schemas"]["TransactionDetail"]["properties"]
    assert {
        "createdBy",
        "senderOrganization",
        "receiverOrganization",
        "send",
        "receive",
        "submissionHash",
        "settlementHash",
        "createdAt",
        "settledAt",
        "failureReason",
    } <= detail_fields.keys()


@pytest.mark.anyio
async def test_send_endpoint_uses_frontend_request_shape(
    monkeypatch: pytest.MonkeyPatch,
    api_dependencies: None,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_transaction(**kwargs: Any) -> TransactionDetail:
        captured.update(kwargs)
        return _detail()

    monkeypatch.setattr(transaction_endpoints, "create_transaction", fake_create_transaction)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/transactions/send",
            headers={"Authorization": "Bearer test"},
            json={
                "receiverOrganizationId": 2,
                "send": {"asset": "USDC", "amount": 500_000_000},
                "receive": {"asset": "BOND", "amount": 5},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["send"]["asset"]["symbol"] == "mUSDC"
    assert body["data"]["submissionHash"] == HASH
    assert captured["uid"] == 1
    assert captured["request"].receiver_organization_id == 2


@pytest.mark.anyio
async def test_verify_static_route_returns_nullable_transaction(
    monkeypatch: pytest.MonkeyPatch,
    api_dependencies: None,
) -> None:
    async def fake_verify_transaction(**_: Any) -> None:
        return None

    monkeypatch.setattr(transaction_endpoints, "verify_transaction", fake_verify_transaction)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/transactions/verify",
            params={"submissionHash": HASH},
        )

    assert response.status_code == 200
    assert response.json()["data"] is None
