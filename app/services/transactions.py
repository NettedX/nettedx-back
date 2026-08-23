"""交易接口业务逻辑。"""

from time import time

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.clients.blockchain import (
    BlockchainClientError,
    fetch_settlement_outcomes,
    submit_trade,
)
from app.core.config import settings
from app.db.enums import OrganizationStatus, TransactionStatus, UserStatus
from app.db.models.organization import Organization
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.schemas.exception import ServiceException
from app.schemas.transactions import (
    AssetAmountObject,
    AssetCode,
    AssetTypeObject,
    CreateTransactionRequest,
    OrganizationSummary,
    TransactionDetail,
)


async def _require_current_organization(db: AsyncSession, uid: int) -> Organization:
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.status != UserStatus.ENABLED:
        raise ServiceException(status_code=401, detail="user is unavailable")

    organization = await db.scalar(
        select(Organization).where(Organization.id == user.organization_id)
    )
    if organization is None or organization.status != OrganizationStatus.ENABLED:
        raise ServiceException(status_code=401, detail="organization is unavailable")
    return organization


def _organization_summary(organization: Organization) -> OrganizationSummary:
    return OrganizationSummary(
        id=organization.id,
        code=organization.code,
        name=organization.name,
    )


def _asset_type(code: str, address: str, chain_id: int) -> AssetTypeObject:
    if code == AssetCode.USDC:
        return AssetTypeObject(
            address=address,
            name="Mock USDC",
            symbol="mUSDC",
            decimals=settings.cash_token_decimals,
            chain_id=chain_id,
        )
    if code == AssetCode.BOND:
        return AssetTypeObject(
            address=address,
            name="Mock Bond",
            symbol="mBOND",
            decimals=settings.bond_token_decimals,
            chain_id=chain_id,
        )
    raise ServiceException(status_code=500, detail="unsupported transaction asset")


def _transaction_detail(transaction: Transaction) -> TransactionDetail:
    return TransactionDetail(
        id=transaction.id,
        created_by=_organization_summary(transaction.created_by),
        sender_organization=_organization_summary(transaction.sender_organization),
        send=AssetAmountObject(
            asset=_asset_type(
                transaction.send_asset,
                transaction.send_asset_address,
                transaction.chain_id,
            ),
            amount=int(transaction.send_amount),
        ),
        receiver_organization=_organization_summary(transaction.receiver_organization),
        receive=AssetAmountObject(
            asset=_asset_type(
                transaction.receive_asset,
                transaction.receive_asset_address,
                transaction.chain_id,
            ),
            amount=int(transaction.receive_amount),
        ),
        status=transaction.status,
        chain_id=transaction.chain_id,
        window_id=int(transaction.window_id),
        submission_hash=transaction.submission_hash,
        settlement_hash=transaction.settlement_hash,
        created_at=transaction.created_at,
        settled_at=transaction.settled_at,
        failure_reason=transaction.failure_reason,
    )


def _configured_asset_address(code: AssetCode) -> str:
    address = (
        settings.mock_usdc_contract_address
        if code == AssetCode.USDC
        else settings.mock_bond_contract_address
    ).strip()
    if not Web3.is_address(address):
        raise ServiceException(status_code=503, detail=f"{code.value} contract is unavailable")
    return Web3.to_checksum_address(address)


async def _refresh_settlement_statuses(
    db: AsyncSession,
    transactions: list[Transaction],
) -> None:
    pending = [
        transaction
        for transaction in transactions
        if transaction.status == TransactionStatus.SUBMITTED
    ]
    if not pending:
        return

    try:
        outcomes = await fetch_settlement_outcomes(
            min(transaction.submission_block for transaction in pending)
        )
    except BlockchainClientError:
        # 查询接口在 RPC 短暂不可用时返回数据库中的最近状态。
        return

    by_window = {outcome.window_id: outcome for outcome in outcomes}
    now = int(time())
    changed = False
    for transaction in pending:
        outcome = by_window.get(int(transaction.window_id))
        if outcome is None:
            continue

        transaction.status = (
            TransactionStatus.SETTLED if outcome.succeeded else TransactionStatus.FAILED
        )
        transaction.settlement_hash = outcome.transaction_hash
        transaction.settled_at = now
        transaction.failure_reason = outcome.reason
        changed = True

    if changed:
        try:
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()


async def get_tradeable_organizations(
    db: AsyncSession,
    uid: int,
) -> list[OrganizationSummary]:
    current = await _require_current_organization(db, uid)
    organizations = list(
        await db.scalars(
            select(Organization)
            .where(
                Organization.status == OrganizationStatus.ENABLED,
                Organization.id != current.id,
            )
            .order_by(Organization.name.asc(), Organization.id.asc())
        )
    )
    return [_organization_summary(organization) for organization in organizations]


async def create_transaction(
    db: AsyncSession,
    uid: int,
    request: CreateTransactionRequest,
) -> TransactionDetail:
    sender = await _require_current_organization(db, uid)
    receiver = await db.scalar(
        select(Organization).where(
            Organization.id == request.receiver_organization_id,
            Organization.status == OrganizationStatus.ENABLED,
        )
    )
    if receiver is None:
        raise ServiceException(status_code=4001, detail="receiver organization is unavailable")
    if receiver.id == sender.id:
        raise ServiceException(status_code=4002, detail="cannot trade with current organization")

    send_address = _configured_asset_address(request.send.asset)
    receive_address = _configured_asset_address(request.receive.asset)

    if request.send.asset == AssetCode.USDC:
        buyer = sender.wallet_address
        seller = receiver.wallet_address
        cash_amount = request.send.amount
        bond_amount = request.receive.amount
    else:
        buyer = receiver.wallet_address
        seller = sender.wallet_address
        cash_amount = request.receive.amount
        bond_amount = request.send.amount

    try:
        submitted = await submit_trade(
            buyer=buyer,
            seller=seller,
            cash_amount=cash_amount,
            bond_amount=bond_amount,
        )
    except BlockchainClientError as exc:
        raise ServiceException(status_code=503, detail="trade submission failed") from exc

    transaction = Transaction(
        created_by_organization_id=sender.id,
        sender_organization_id=sender.id,
        receiver_organization_id=receiver.id,
        send_asset=request.send.asset.value,
        send_asset_address=send_address.lower(),
        send_amount=str(request.send.amount),
        receive_asset=request.receive.asset.value,
        receive_asset_address=receive_address.lower(),
        receive_amount=str(request.receive.amount),
        status=TransactionStatus.SUBMITTED,
        chain_id=submitted.chain_id,
        window_id=str(submitted.window_id),
        trade_id=str(submitted.trade_id),
        submission_hash=submitted.transaction_hash.lower(),
        submission_block=submitted.block_number,
        created_at=int(time()),
        created_by=sender,
        sender_organization=sender,
        receiver_organization=receiver,
    )
    db.add(transaction)
    try:
        await db.commit()
        await db.refresh(transaction)
    except SQLAlchemyError as exc:
        await db.rollback()
        raise ServiceException(status_code=500, detail="failed to save transaction") from exc

    return _transaction_detail(transaction)


async def list_transactions(
    db: AsyncSession,
    uid: int,
    is_related: bool,
) -> list[TransactionDetail]:
    current = await _require_current_organization(db, uid)
    query = select(Transaction)
    if is_related:
        query = query.where(
            or_(
                Transaction.sender_organization_id == current.id,
                Transaction.receiver_organization_id == current.id,
            )
        )
    transactions = list(await db.scalars(query.order_by(Transaction.created_at.desc())))
    await _refresh_settlement_statuses(db, transactions)
    return [_transaction_detail(transaction) for transaction in transactions]


async def get_transaction(
    db: AsyncSession,
    uid: int,
    transaction_id: int,
) -> TransactionDetail:
    current = await _require_current_organization(db, uid)
    transaction = await db.scalar(select(Transaction).where(Transaction.id == transaction_id))
    if transaction is None:
        raise ServiceException(status_code=404, detail="transaction not found")
    if current.id not in {
        transaction.sender_organization_id,
        transaction.receiver_organization_id,
    }:
        raise ServiceException(status_code=403, detail="transaction access denied")

    await _refresh_settlement_statuses(db, [transaction])
    return _transaction_detail(transaction)


async def verify_transaction(
    db: AsyncSession,
    submission_hash: str,
) -> TransactionDetail | None:
    transaction = await db.scalar(
        select(Transaction).where(
            func.lower(Transaction.submission_hash) == submission_hash.lower()
        )
    )
    if transaction is None:
        return None
    await _refresh_settlement_statuses(db, [transaction])
    return _transaction_detail(transaction)
