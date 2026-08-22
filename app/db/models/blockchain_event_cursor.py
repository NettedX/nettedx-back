"""定义链上事件增量同步游标。"""

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BlockchainEventCursor(Base):
    __tablename__ = "blockchain_event_cursors"
    __table_args__ = (
        UniqueConstraint(
            "chain_id",
            "contract_address",
            "event_name",
            name="uq_blockchain_event_cursor",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contract_address: Mapped[str] = mapped_column(String(42), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_synced_block: Mapped[int] = mapped_column(BigInteger, nullable=False)
