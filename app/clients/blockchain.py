"""通过 Ethereum JSON-RPC 读取 Dashboard 所需的链上数据。"""

import asyncio
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
class RawDashboardAssetState:
    """一种 Dashboard 资产的元数据、账户余额和 Buffer 债务。"""

    address: str
    name: str
    symbol: str
    decimals: int
    balance: int
    liquidity_buffer_debt: int


@dataclass(frozen=True)
class RawDashboardChainState:
    """同一区块最新状态下的 Dashboard 链上快照。"""

    chain_id: int
    net_positions: list[RawBankNetPosition]
    assets: list[RawDashboardAssetState]


@dataclass(frozen=True)
class RawTradeEventChainStatus:
    """TradeSubmitted 事件索引所需的链状态。"""

    chain_id: int
    contract_address: str
    latest_block: int


@dataclass(frozen=True)
class RawTradeSubmittedEvent:
    """解码后的单个 Netting.TradeSubmitted 日志。"""

    block_number: int
    transaction_hash: str
    log_index: int
    window_id: int
    trade_id: int
    buyer: str
    seller: str
    cash_amount: int
    bond_amount: int


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


def _load_abi(filename: str) -> list[dict[str, Any]]:
    """从应用包中加载后端所需的最小合约 ABI。"""

    abi_path = files("app.contracts").joinpath(filename)
    abi = json.loads(abi_path.read_text(encoding="utf-8"))

    if not isinstance(abi, list):
        raise RuntimeError("invalid netting abi")

    return abi


NETTING_ABI = _load_abi("netting_abi.json")
ERC20_ABI = _load_abi("erc20_abi.json")
LIQUIDITY_BUFFER_ABI = _load_abi("liquidity_buffer_abi.json")
DASHBOARD_SNAPSHOT_MAX_ATTEMPTS = 3


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

    return _parse_bank_net_positions(result)


def _parse_bank_net_positions(result: Any) -> list[RawBankNetPosition]:
    """校验并转换 getBankNetPositions 的返回值。"""

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


def _require_blockchain_configuration(*addresses: str) -> tuple[str, list[str]]:
    """校验 RPC 与一组配置的合约地址。"""

    rpc_url = settings.blockchain_rpc_url.strip()
    if not rpc_url or any(not address.strip() for address in addresses):
        raise BlockchainClientError("blockchain configuration is incomplete")

    checksum_addresses = [
        _normalize_dashboard_address(address, "invalid contract address") for address in addresses
    ]
    return rpc_url, checksum_addresses


async def fetch_dashboard_chain_state(bank: str) -> RawDashboardChainState:
    """读取同一结算窗口的净头寸、资产余额和实际 Buffer 欠款。"""

    checksum_bank = _normalize_dashboard_address(bank, "invalid bank wallet address")
    rpc_url, addresses = _require_blockchain_configuration(
        settings.netting_contract_address,
        settings.liquidity_buffer_contract_address,
        settings.mock_usdc_contract_address,
        settings.mock_bond_contract_address,
    )
    netting_address, buffer_address, usdc_address, bond_address = addresses
    provider = AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 10})
    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")

        codes = await asyncio.gather(
            *(web3.eth.get_code(address) for address in addresses),
        )
        if any(not code for code in codes):
            raise BlockchainClientError("dashboard contract is not deployed")

        netting = web3.eth.contract(address=netting_address, abi=NETTING_ABI)
        liquidity_buffer = web3.eth.contract(
            address=buffer_address,
            abi=LIQUIDITY_BUFFER_ABI,
        )
        tokens = [
            web3.eth.contract(address=usdc_address, abi=ERC20_ABI),
            web3.eth.contract(address=bond_address, abi=ERC20_ABI),
        ]

        chain_id_result, snapshot = await asyncio.gather(
            web3.eth.chain_id,
            _fetch_consistent_dashboard_snapshot(
                netting=netting,
                liquidity_buffer=liquidity_buffer,
                tokens=tokens,
                asset_addresses=[usdc_address, bond_address],
                bank=checksum_bank,
            ),
        )
        positions_result, asset_results = snapshot
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to read dashboard chain state") from exc
    finally:
        await provider.disconnect()

    chain_id = _parse_dashboard_uint(chain_id_result, "invalid chain id")
    if chain_id == 0:
        raise BlockchainClientError("invalid chain id")

    return RawDashboardChainState(
        chain_id=chain_id,
        net_positions=_parse_bank_net_positions(positions_result),
        assets=list(asset_results),
    )


async def _fetch_consistent_dashboard_snapshot(
    *,
    netting: Any,
    liquidity_buffer: Any,
    tokens: list[Any],
    asset_addresses: list[str],
    bank: str,
) -> tuple[Any, list[RawDashboardAssetState]]:
    """窗口切换时重读，避免把上一窗口净额与结算后余额拼成一个响应。"""

    for _ in range(DASHBOARD_SNAPSHOT_MAX_ATTEMPTS):
        window_before = _parse_dashboard_uint(
            await netting.functions.currentWindowId().call(),
            "invalid current window id",
        )
        positions_result, *asset_results = await asyncio.gather(
            netting.functions.getBankNetPositions(bank).call(),
            *(
                _fetch_dashboard_asset_state(
                    token=token,
                    asset_address=asset_address,
                    liquidity_buffer=liquidity_buffer,
                    bank=bank,
                )
                for token, asset_address in zip(
                    tokens,
                    asset_addresses,
                    strict=True,
                )
            ),
        )
        window_after = _parse_dashboard_uint(
            await netting.functions.currentWindowId().call(),
            "invalid current window id",
        )

        if window_before == window_after:
            return positions_result, asset_results

    raise BlockchainClientError("dashboard settlement window changed during read")


async def _fetch_dashboard_asset_state(
    *,
    token: Any,
    asset_address: str,
    liquidity_buffer: Any,
    bank: str,
) -> RawDashboardAssetState:
    """读取单个 ERC20 的展示元数据、余额和实际债务。"""

    name, symbol, decimals, balance, debt = await asyncio.gather(
        token.functions.name().call(),
        token.functions.symbol().call(),
        token.functions.decimals().call(),
        token.functions.balanceOf(bank).call(),
        liquidity_buffer.functions.debt(bank, asset_address).call(),
    )

    if not isinstance(name, str) or not name:
        raise BlockchainClientError("invalid asset name")
    if not isinstance(symbol, str) or not symbol:
        raise BlockchainClientError("invalid asset symbol")

    parsed_decimals = _parse_dashboard_uint(decimals, "invalid asset decimals")
    if parsed_decimals > 255:
        raise BlockchainClientError("invalid asset decimals")

    return RawDashboardAssetState(
        address=asset_address,
        name=name,
        symbol=symbol,
        decimals=parsed_decimals,
        balance=_parse_dashboard_uint(balance, "invalid asset balance"),
        liquidity_buffer_debt=_parse_dashboard_uint(debt, "invalid buffer debt"),
    )


async def fetch_trade_event_chain_status() -> RawTradeEventChainStatus:
    """读取 TradeSubmitted 索引使用的 chain ID、合约地址和最新区块。"""

    rpc_url, addresses = _require_blockchain_configuration(settings.netting_contract_address)
    contract_address = addresses[0]
    provider = AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 10})
    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")
        code, chain_id, latest_block = await asyncio.gather(
            web3.eth.get_code(contract_address),
            web3.eth.chain_id,
            web3.eth.block_number,
        )
        if not code:
            raise BlockchainClientError("netting contract is not deployed")
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to read trade event chain status") from exc
    finally:
        await provider.disconnect()

    parsed_chain_id = _parse_dashboard_uint(chain_id, "invalid chain id")
    parsed_latest_block = _parse_dashboard_uint(latest_block, "invalid latest block")
    if parsed_chain_id == 0:
        raise BlockchainClientError("invalid chain id")

    return RawTradeEventChainStatus(
        chain_id=parsed_chain_id,
        contract_address=contract_address.lower(),
        latest_block=parsed_latest_block,
    )


async def fetch_trade_submitted_events(
    from_block: int,
    to_block: int,
) -> list[RawTradeSubmittedEvent]:
    """读取并解码闭区间内的 TradeSubmitted 事件。"""

    if from_block < 0 or to_block < from_block:
        raise BlockchainClientError("invalid trade event block range")

    rpc_url, addresses = _require_blockchain_configuration(settings.netting_contract_address)
    contract_address = addresses[0]
    provider = AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 10})
    web3 = AsyncWeb3(provider)

    try:
        if not await web3.is_connected():
            raise BlockchainClientError("blockchain rpc is unavailable")
        contract = web3.eth.contract(address=contract_address, abi=NETTING_ABI)
        logs = await contract.events.TradeSubmitted().get_logs(
            from_block=from_block,
            to_block=to_block,
        )
    except BlockchainClientError:
        raise
    except Exception as exc:
        raise BlockchainClientError("failed to read TradeSubmitted events") from exc
    finally:
        await provider.disconnect()

    return _parse_trade_submitted_logs(logs)


def _parse_trade_submitted_logs(logs: Any) -> list[RawTradeSubmittedEvent]:
    """校验并转换 Web3 解码后的 TradeSubmitted 日志。"""

    events: list[RawTradeSubmittedEvent] = []
    for log in logs:
        try:
            args = log["args"]
            transaction_hash = Web3.to_hex(log["transactionHash"])
            event = RawTradeSubmittedEvent(
                block_number=_parse_dashboard_uint(
                    log["blockNumber"],
                    "invalid trade event block number",
                ),
                transaction_hash=transaction_hash,
                log_index=_parse_dashboard_uint(log["logIndex"], "invalid trade event log index"),
                window_id=_parse_dashboard_uint(args["windowId"], "invalid trade event window id"),
                trade_id=_parse_dashboard_uint(args["tradeId"], "invalid trade event trade id"),
                buyer=_normalize_dashboard_address(
                    args["buyer"],
                    "invalid trade event buyer",
                ).lower(),
                seller=_normalize_dashboard_address(
                    args["seller"],
                    "invalid trade event seller",
                ).lower(),
                cash_amount=_parse_dashboard_uint(
                    args["cashAmount"],
                    "invalid trade event cash amount",
                ),
                bond_amount=_parse_dashboard_uint(
                    args["bondAmount"],
                    "invalid trade event bond amount",
                ),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise BlockchainClientError("invalid TradeSubmitted event") from exc

        if not transaction_hash.startswith("0x") or len(transaction_hash) != 66:
            raise BlockchainClientError("invalid trade event transaction hash")
        events.append(event)

    return events


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
