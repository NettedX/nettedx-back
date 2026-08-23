"""交易业务记录。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import TransactionStatus

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "chain_id",
            "submission_hash",
            name="uq_transactions_chain_submission_hash",
        ),
        Index("ix_transactions_sender_organization_id", "sender_organization_id"),
        Index("ix_transactions_receiver_organization_id", "receiver_organization_id"),
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_by_organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sender_organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receiver_organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    send_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    send_asset_address: Mapped[str] = mapped_column(String(42), nullable=False)
    send_amount: Mapped[str] = mapped_column(String(78), nullable=False)
    receive_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    receive_asset_address: Mapped[str] = mapped_column(String(42), nullable=False)
    receive_amount: Mapped[str] = mapped_column(String(78), nullable=False)

    status: Mapped[TransactionStatus] = mapped_column(
        SqlEnum(
            TransactionStatus,
            values_callable=lambda enum_class: [member.value for member in enum_class],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=TransactionStatus.SUBMITTED,
        server_default=TransactionStatus.SUBMITTED.value,
    )
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    window_id: Mapped[str] = mapped_column(String(78), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(78), nullable=False)
    submission_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    submission_block: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settlement_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settled_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by: Mapped[Organization] = relationship(
        foreign_keys=[created_by_organization_id],
        lazy="joined",
    )
    sender_organization: Mapped[Organization] = relationship(
        foreign_keys=[sender_organization_id],
        lazy="joined",
    )
    receiver_organization: Mapped[Organization] = relationship(
        foreign_keys=[receiver_organization_id],
        lazy="joined",
    )
