"""定义用户数据库模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SqlEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import UserStatus

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            name="uq_users_organization_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="用户显示名称",
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="operator",
        server_default="operator",
        comment="用户角色",
    )
    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),  # 机构下面还有用户时，不允许误删机构
        nullable=False,
        comment="用户所属机构ID",
    )
    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(
            UserStatus,
            values_callable=lambda enum_class: [member.value for member in enum_class],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=UserStatus.ENABLED,
        server_default=UserStatus.ENABLED.value,
        comment="用户状态",
    )
    organization: Mapped[Organization] = relationship(
        back_populates="users",
    )
