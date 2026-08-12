"""定义 SIWE 一次性 nonce 数据库模型。"""

from sqlalchemy import BigInteger, Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# 后端签发且只能消费一次的 SIWE nonce
class SiweNonce(Base):
    __tablename__ = "siwe_nonces"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    nonce: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        comment="SIWE消息中的随机nonce",
    )
    wallet_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False,
        index=True,
    )
    chain_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="EIP-155 Chain ID",
    )
    issued_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="签发时间，Unix秒级时间戳",
    )
    expires_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="过期时间，Unix秒级时间戳",
    )
    used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="nonce是否已经被消费",
    )
    used_at: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="消费时间，Unix秒级时间戳",
    )
