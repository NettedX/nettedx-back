from types import SimpleNamespace
from typing import Any

import pytest

from app.clients.blockchain import _send_trade_transaction
from app.core.config import settings


class FakeFunction:
    def __init__(self) -> None:
        self.built_transaction: dict[str, Any] | None = None
        self.transact_transaction: dict[str, Any] | None = None

    async def build_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        self.built_transaction = transaction
        return transaction

    async def transact(self, transaction: dict[str, Any]) -> bytes:
        self.transact_transaction = transaction
        return b"unlocked-hash"


class FakeSigner:
    address = "0x1111111111111111111111111111111111111111"

    def __init__(self) -> None:
        self.signed_transaction: dict[str, Any] | None = None

    def sign_transaction(self, transaction: dict[str, Any]) -> Any:
        self.signed_transaction = transaction
        return SimpleNamespace(raw_transaction=b"signed-transaction")


@pytest.mark.anyio
async def test_unlocked_trade_uses_configured_large_gas_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function = FakeFunction()
    eth = SimpleNamespace(accounts=_accounts())
    web3 = SimpleNamespace(eth=eth)
    monkeypatch.setattr(settings, "blockchain_relayer_private_key", "")
    monkeypatch.setattr(settings, "blockchain_trade_gas_limit", 5_000_000)

    transaction_hash = await _send_trade_transaction(web3=web3, function=function)

    assert transaction_hash == b"unlocked-hash"
    assert function.transact_transaction == {
        "from": "0x2222222222222222222222222222222222222222",
        "gas": 5_000_000,
    }


@pytest.mark.anyio
async def test_signed_trade_uses_configured_large_gas_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function = FakeFunction()
    signer = FakeSigner()

    async def get_transaction_count(address: str, block: str) -> int:
        assert address == signer.address
        assert block == "pending"
        return 7

    async def send_raw_transaction(raw_transaction: bytes) -> bytes:
        assert raw_transaction == b"signed-transaction"
        return b"signed-hash"

    async def chain_id() -> int:
        return 31337

    eth = SimpleNamespace(
        account=SimpleNamespace(from_key=lambda _: signer),
        get_transaction_count=get_transaction_count,
        send_raw_transaction=send_raw_transaction,
        chain_id=chain_id(),
    )
    web3 = SimpleNamespace(eth=eth)
    monkeypatch.setattr(settings, "blockchain_relayer_private_key", "test-private-key")
    monkeypatch.setattr(settings, "blockchain_trade_gas_limit", 5_000_000)

    transaction_hash = await _send_trade_transaction(web3=web3, function=function)

    assert transaction_hash == b"signed-hash"
    assert function.built_transaction == {
        "from": signer.address,
        "nonce": 7,
        "chainId": 31337,
        "gas": 5_000_000,
    }
    assert signer.signed_transaction == function.built_transaction


async def _accounts() -> list[str]:
    return ["0x2222222222222222222222222222222222222222"]
