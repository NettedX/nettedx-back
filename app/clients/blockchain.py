"""通过 Ethereum JSON-RPC 读取 Netting 合约的公开指标。"""

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from web3 import AsyncHTTPProvider, AsyncWeb3, Web3

from app.core.config import settings


class BlockchainClientError(RuntimeError):
    """区块链配置、连接或合约调用失败。"""


@dataclass(frozen=True)
class RawPublicAnalyticsMetrics:
    """Netting 合约返回的四项原始 uint256 数据。"""

    total_settlement_amount: int
    total_trade_count: int
    liquidity_saved: int
    obligation_reduction: int


def _load_netting_abi() -> list[dict[str, Any]]:
    """从应用包中加载后端所需的最小 Netting ABI。"""

    abi_path = files("app.contracts").joinpath("netting_abi.json")
    abi = json.loads(abi_path.read_text(encoding="utf-8"))

    if not isinstance(abi, list):
        raise RuntimeError("invalid netting abi")

    return abi


NETTING_ABI = _load_netting_abi()


async def fetch_public_analytics_metrics() -> RawPublicAnalyticsMetrics:
    """调用 Netting 合约，读取当前窗口的四项首页公开指标。"""

    rpc_url = settings.blockchain_rpc_url.strip()
    contract_address = settings.netting_contract_address.strip()

    if not rpc_url or not contract_address:
        raise BlockchainClientError("blockchain configuration is incomplete")

    if not Web3.is_address(contract_address):
        raise BlockchainClientError("invalid netting contract address")

    checksum_address = Web3.to_checksum_address(contract_address)
    provider = AsyncHTTPProvider(
        rpc_url,
        request_kwargs={"timeout": 10},
    )

    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")

        contract_code = await web3.eth.get_code(checksum_address)
        if not contract_code:
            raise BlockchainClientError("netting contract is not deployed")

        contract = web3.eth.contract(
            address=checksum_address,
            abi=NETTING_ABI,
        )
        result = await contract.functions.getPublicAnalyticsMetrics().call()
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to read public analytics metrics") from exc
    finally:
        await provider.disconnect()

    if not isinstance(result, (list, tuple)) or len(result) != 4:
        raise BlockchainClientError("invalid public analytics contract result")

    (
        total_settlement_amount,
        total_trade_count,
        liquidity_saved,
        obligation_reduction,
    ) = (int(value) for value in result)

    if (
        min(
            total_settlement_amount,
            total_trade_count,
            liquidity_saved,
            obligation_reduction,
        )
        < 0
    ):
        raise BlockchainClientError("invalid negative contract metric")

    return RawPublicAnalyticsMetrics(
        total_settlement_amount=total_settlement_amount,
        total_trade_count=total_trade_count,
        liquidity_saved=liquidity_saved,
        obligation_reduction=obligation_reduction,
    )
