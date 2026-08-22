"""保存 Netting.TradeSubmitted 事件，用于用户累计交易统计。"""

from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TradeSubmittedEvent(Base):
    __tablename__ = "trade_submitted_events"
    __table_args__ = (
        UniqueConstraint(
            "chain_id",
            "contract_address",
            "transaction_hash",
            "log_index",
            name="uq_trade_submitted_event_log",
        ),
        Index("ix_trade_submitted_events_buyer", "buyer"),
        Index("ix_trade_submitted_events_seller", "seller"),
        Index("ix_trade_submitted_events_block_number", "block_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contract_address: Mapped[str] = mapped_column(String(42), nullable=False)
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    log_index: Mapped[int] = mapped_column(Integer, nullable=False)
    window_id: Mapped[str] = mapped_column(String(78), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(78), nullable=False)
    buyer: Mapped[str] = mapped_column(String(42), nullable=False)
    seller: Mapped[str] = mapped_column(String(42), nullable=False)
    cash_amount: Mapped[str] = mapped_column(String(78), nullable=False)
    bond_amount: Mapped[str] = mapped_column(String(78), nullable=False)
