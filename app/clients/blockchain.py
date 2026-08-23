"""通过 Ethereum JSON-RPC 读取 Netting 合约一些原始数据。"""

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


@dataclass(frozen=True)
class RawSettlementWindowForecast:
    """Netting 合约返回的结算窗口预测原始数据。"""

    window_id: int
    settlement_block: int
    blocks_remaining: int


@dataclass(frozen=True)  # frozen=True表示对象创建之后不能随意修改
class RawBankNetPosition:
    """Netting 合约返回的单项银行净结算头寸。"""

    asset: str
    payable_amount: int
    receivable_amount: int


@dataclass(frozen=True)
class RawSettlementAssetRequirement:
    """Netting 合约返回的单项结算资产需求。"""

    asset: str
    required_amount: int


@dataclass(frozen=True)
class RawLiquidityShortfall:
    """Netting 合约返回的单项银行流动性缺口。"""

    asset: str
    required_amount: int
    available_balance: int
    borrow_amount: int


@dataclass(frozen=True)
class RawSubmittedTrade:
    """submitTrade 成功回执中的 TradeSubmitted 事件。"""

    chain_id: int
    window_id: int
    trade_id: int
    transaction_hash: str
    block_number: int


@dataclass(frozen=True)
class RawSettlementOutcome:
    """某个结算窗口的成功或失败事件。"""

    window_id: int
    succeeded: bool
    transaction_hash: str
    block_number: int
    reason: str | None


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


async def _call_dashboard_function(
    function_name: str,
    *args: Any,
) -> Any:
    """调用 Netting 合约中的 Dashboard 只读函数。"""

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
        function = getattr(contract.functions, function_name)
        return await function(*args).call()
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError(f"failed to call dashboard function: {function_name}") from exc
    finally:
        await provider.disconnect()


async def fetch_settlement_window_forecast() -> RawSettlementWindowForecast:
    """读取下一结算窗口、目标区块和剩余区块数。"""

    result = await _call_dashboard_function("getSettlementWindowForecast")

    if not isinstance(result, (list, tuple)) or len(result) != 3:
        raise BlockchainClientError("invalid settlement window forecast result")

    try:
        window_id, settlement_block, blocks_remaining = (int(value) for value in result)
    except (TypeError, ValueError) as exc:
        raise BlockchainClientError("invalid settlement window forecast result") from exc

    if min(window_id, settlement_block, blocks_remaining) < 0:
        raise BlockchainClientError("invalid settlement window forecast result")

    return RawSettlementWindowForecast(
        window_id=window_id,
        settlement_block=settlement_block,
        blocks_remaining=blocks_remaining,
    )


def _normalize_dashboard_address(
    address: str,
    error_message: str,
) -> str:
    """校验 Dashboard 使用的地址并转换为 checksum 格式。"""

    address = address.strip()

    if not Web3.is_address(address):
        raise BlockchainClientError(error_message)

    return Web3.to_checksum_address(address)


def _parse_dashboard_uint(
    value: Any,
    error_message: str,
) -> int:
    """将 Solidity uint 返回值转换为非负整数。"""

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise BlockchainClientError(error_message) from exc

    if parsed_value < 0:
        raise BlockchainClientError(error_message)

    return parsed_value


async def fetch_bank_net_positions(
    bank: str,
) -> list[RawBankNetPosition]:
    """读取银行按金融产品区分的应付和应收头寸。"""

    checksum_bank = _normalize_dashboard_address(
        bank,
        "invalid bank wallet address",
    )
    result = await _call_dashboard_function(
        "getBankNetPositions",
        checksum_bank,
    )

    if not isinstance(result, (list, tuple)):
        raise BlockchainClientError("invalid bank net positions result")

    positions: list[RawBankNetPosition] = []

    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise BlockchainClientError("invalid bank net position item")

        asset = _normalize_dashboard_address(
            item[0],
            "invalid asset address in bank net positions",
        )
        payable_amount = _parse_dashboard_uint(
            item[1],
            "invalid payable amount in bank net positions",
        )
        receivable_amount = _parse_dashboard_uint(
            item[2],
            "invalid receivable amount in bank net positions",
        )

        if payable_amount > 0 and receivable_amount > 0:
            raise BlockchainClientError("invalid simultaneous payable and receivable amounts")

        positions.append(
            RawBankNetPosition(
                asset=asset,
                payable_amount=payable_amount,
                receivable_amount=receivable_amount,
            )
        )

    return positions


async def fetch_bank_settlement_asset_requirements(
    bank: str,
) -> list[RawSettlementAssetRequirement]:
    """读取银行本轮结算必须准备的金融产品及数量。"""

    checksum_bank = _normalize_dashboard_address(
        bank,
        "invalid bank wallet address",
    )
    result = await _call_dashboard_function(
        "getBankSettlementAssetRequirements",
        checksum_bank,
    )

    if not isinstance(result, (list, tuple)):
        raise BlockchainClientError("invalid settlement asset requirements result")

    requirements: list[RawSettlementAssetRequirement] = []

    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise BlockchainClientError("invalid settlement asset requirement item")

        asset = _normalize_dashboard_address(
            item[0],
            "invalid asset address in settlement requirements",
        )
        required_amount = _parse_dashboard_uint(
            item[1],
            "invalid required amount in settlement requirements",
        )

        requirements.append(
            RawSettlementAssetRequirement(
                asset=asset,
                required_amount=required_amount,
            )
        )

    return requirements


async def fetch_bank_liquidity_shortfalls(
    bank: str,
) -> list[RawLiquidityShortfall]:
    """读取银行结算所需数量、余额和预计借款额。"""

    checksum_bank = _normalize_dashboard_address(
        bank,
        "invalid bank wallet address",
    )
    result = await _call_dashboard_function(
        "getBankLiquidityShortfalls",
        checksum_bank,
    )

    if not isinstance(result, (list, tuple)):
        raise BlockchainClientError("invalid bank liquidity shortfalls result")

    shortfalls: list[RawLiquidityShortfall] = []

    for item in result:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            raise BlockchainClientError("invalid bank liquidity shortfall item")

        asset = _normalize_dashboard_address(
            item[0],
            "invalid asset address in liquidity shortfalls",
        )
        required_amount = _parse_dashboard_uint(
            item[1],
            "invalid required amount in liquidity shortfalls",
        )
        available_balance = _parse_dashboard_uint(
            item[2],
            "invalid available balance in liquidity shortfalls",
        )
        borrow_amount = _parse_dashboard_uint(
            item[3],
            "invalid borrow amount in liquidity shortfalls",
        )

        shortfalls.append(
            RawLiquidityShortfall(
                asset=asset,
                required_amount=required_amount,
                available_balance=available_balance,
                borrow_amount=borrow_amount,
            )
        )

    return shortfalls


def _validate_transaction_address(address: str, field_name: str) -> str:
    address = address.strip()
    if not Web3.is_address(address):
        raise BlockchainClientError(f"invalid {field_name} address")
    return Web3.to_checksum_address(address)


def _validate_transaction_amount(amount: int, field_name: str) -> int:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise BlockchainClientError(f"invalid {field_name} amount")
    if amount >= 2**256:
        raise BlockchainClientError(f"invalid {field_name} amount")
    return amount


async def submit_trade(
    buyer: str,
    seller: str,
    cash_amount: int,
    bond_amount: int,
) -> RawSubmittedTrade:
    """使用配置的 relayer（或开发节点解锁账户）提交一笔已撮合交易。"""

    rpc_url = settings.blockchain_rpc_url.strip()
    contract_address = settings.netting_contract_address.strip()
    if not rpc_url or not contract_address:
        raise BlockchainClientError("blockchain configuration is incomplete")

    checksum_contract = _validate_transaction_address(contract_address, "netting contract")
    checksum_buyer = _validate_transaction_address(buyer, "buyer")
    checksum_seller = _validate_transaction_address(seller, "seller")
    if checksum_buyer == checksum_seller:
        raise BlockchainClientError("buyer and seller must be different")

    cash_amount = _validate_transaction_amount(cash_amount, "cash")
    bond_amount = _validate_transaction_amount(bond_amount, "bond")

    provider = AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 10})
    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")

        contract_code = await web3.eth.get_code(checksum_contract)
        if not contract_code:
            raise BlockchainClientError("netting contract is not deployed")

        contract = web3.eth.contract(address=checksum_contract, abi=NETTING_ABI)
        function = contract.functions.submitTrade(
            checksum_buyer,
            checksum_seller,
            cash_amount,
            bond_amount,
        )

        private_key = settings.blockchain_relayer_private_key.strip()
        if private_key:
            try:
                account = web3.eth.account.from_key(private_key)
            except Exception as exc:
                raise BlockchainClientError("invalid relayer private key") from exc

            nonce = await web3.eth.get_transaction_count(account.address, "pending")
            transaction = await function.build_transaction(
                {
                    "from": account.address,
                    "nonce": nonce,
                    "chainId": await web3.eth.chain_id,
                }
            )
            signed = account.sign_transaction(transaction)
            raw_transaction = getattr(signed, "raw_transaction", None)
            if raw_transaction is None:
                raw_transaction = signed.rawTransaction
            transaction_hash = await web3.eth.send_raw_transaction(raw_transaction)
        else:
            accounts = await web3.eth.accounts
            if not accounts:
                raise BlockchainClientError("no unlocked relayer account is available")
            transaction_hash = await function.transact({"from": accounts[0]})

        receipt = await web3.eth.wait_for_transaction_receipt(
            transaction_hash,
            timeout=settings.blockchain_transaction_timeout_seconds,
        )
        if int(receipt.get("status", 0)) != 1:
            raise BlockchainClientError("trade submission reverted")

        events = contract.events.TradeSubmitted().process_receipt(receipt)
        if len(events) != 1:
            raise BlockchainClientError("missing TradeSubmitted event")

        event = events[0]
        args = event["args"]
        return RawSubmittedTrade(
            chain_id=int(await web3.eth.chain_id),
            window_id=_parse_dashboard_uint(args["windowId"], "invalid trade window id"),
            trade_id=_parse_dashboard_uint(args["tradeId"], "invalid trade id"),
            transaction_hash=Web3.to_hex(receipt["transactionHash"]),
            block_number=_parse_dashboard_uint(
                receipt["blockNumber"],
                "invalid trade block number",
            ),
        )
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to submit trade") from exc
    finally:
        await provider.disconnect()


async def fetch_settlement_outcomes(from_block: int) -> list[RawSettlementOutcome]:
    """读取指定区块之后的窗口结算结果，供交易查询时刷新状态。"""

    if from_block < 0:
        raise BlockchainClientError("invalid settlement event start block")

    rpc_url = settings.blockchain_rpc_url.strip()
    contract_address = settings.netting_contract_address.strip()
    if not rpc_url or not contract_address:
        raise BlockchainClientError("blockchain configuration is incomplete")

    checksum_contract = _validate_transaction_address(contract_address, "netting contract")
    provider = AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 10})
    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")

        contract_code = await web3.eth.get_code(checksum_contract)
        if not contract_code:
            raise BlockchainClientError("netting contract is not deployed")

        contract = web3.eth.contract(address=checksum_contract, abi=NETTING_ABI)
        succeeded_logs = await contract.events.SettlementSucceeded().get_logs(
            from_block=from_block,
            to_block="latest",
        )
        reverted_logs = await contract.events.SettlementReverted().get_logs(
            from_block=from_block,
            to_block="latest",
        )
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to read settlement events") from exc
    finally:
        await provider.disconnect()

    outcomes = [
        RawSettlementOutcome(
            window_id=_parse_dashboard_uint(
                log["args"]["windowId"],
                "invalid settlement window id",
            ),
            succeeded=True,
            transaction_hash=Web3.to_hex(log["transactionHash"]),
            block_number=_parse_dashboard_uint(
                log["blockNumber"],
                "invalid settlement block number",
            ),
            reason=None,
        )
        for log in succeeded_logs
    ]
    outcomes.extend(
        RawSettlementOutcome(
            window_id=_parse_dashboard_uint(
                log["args"]["windowId"],
                "invalid settlement window id",
            ),
            succeeded=False,
            transaction_hash=Web3.to_hex(log["transactionHash"]),
            block_number=_parse_dashboard_uint(
                log["blockNumber"],
                "invalid settlement block number",
            ),
            reason=str(log["args"].get("reason") or "settlement reverted"),
        )
        for log in reverted_logs
    )
    return sorted(outcomes, key=lambda item: item.block_number)
