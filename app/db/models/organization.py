"""定义机构数据库模型"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import OrganizationStatus

if TYPE_CHECKING:
    from app.db.models.user import User


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,  # 自增
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="机构唯一代码",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="机构名称",
    )
    status: Mapped[OrganizationStatus] = mapped_column(
        SqlEnum(
            OrganizationStatus,
            values_callable=lambda enum_class: [member.value for member in enum_class],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=OrganizationStatus.ENABLED,
        server_default=OrganizationStatus.ENABLED.value,
        comment="机构状态",
    )

    users: Mapped[list[User]] = relationship(
        back_populates="organization",
    )
