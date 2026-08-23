from types import SimpleNamespace
from typing import Any

import pytest

from app.clients.blockchain import RawSubmittedTrade
from app.core.config import settings
from app.db.enums import OrganizationStatus, UserStatus
from app.db.models.organization import Organization
from app.schemas.transactions import CreateTransactionRequest
from app.services import transactions as transaction_service


class FakeSession:
    def __init__(self, scalar_results: list[Any]) -> None:
        self.scalar_results = scalar_results
        self.added: list[Any] = []
        self.commits = 0

    async def scalar(self, _: Any) -> Any:
        return self.scalar_results.pop(0)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, value: Any) -> None:
        value.id = 101

    async def rollback(self) -> None:
        pass


@pytest.mark.anyio
async def test_bond_sender_is_mapped_to_contract_seller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = Organization(
        id=1,
        code="BANK_A",
        name="Bank A",
        wallet_address=f"0x{'11' * 20}",
        status=OrganizationStatus.ENABLED,
    )
    receiver = Organization(
        id=2,
        code="BANK_B",
        name="Bank B",
        wallet_address=f"0x{'22' * 20}",
        status=OrganizationStatus.ENABLED,
    )
    user = SimpleNamespace(
        id=10,
        organization_id=sender.id,
        status=UserStatus.ENABLED,
    )
    db = FakeSession([user, sender, receiver])
    captured: dict[str, Any] = {}

    async def fake_submit_trade(**kwargs: Any) -> RawSubmittedTrade:
        captured.update(kwargs)
        return RawSubmittedTrade(
            chain_id=31337,
            window_id=4,
            trade_id=9,
            transaction_hash=f"0x{'33' * 32}",
            block_number=100,
        )

    monkeypatch.setattr(transaction_service, "submit_trade", fake_submit_trade)
    monkeypatch.setattr(settings, "mock_usdc_contract_address", f"0x{'44' * 20}")
    monkeypatch.setattr(settings, "mock_bond_contract_address", f"0x{'55' * 20}")

    request = CreateTransactionRequest.model_validate(
        {
            "receiverOrganizationId": receiver.id,
            "send": {"asset": "BOND", "amount": 5},
            "receive": {"asset": "USDC", "amount": 500_000_000},
        }
    )
    detail = await transaction_service.create_transaction(
        db=db,  # type: ignore[arg-type]
        uid=user.id,
        request=request,
    )

    assert captured == {
        "buyer": receiver.wallet_address,
        "seller": sender.wallet_address,
        "cash_amount": 500_000_000,
        "bond_amount": 5,
    }
    assert detail.id == 101
    assert detail.send.asset.symbol == "mBOND"
    assert detail.receive.asset.symbol == "mUSDC"
    assert detail.window_id == 4
    assert db.commits == 1
