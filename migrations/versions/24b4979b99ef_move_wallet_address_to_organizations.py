"""move wallet address to organizations

Revision ID: 24b4979b99ef
Revises: 90a82456a4f1
Create Date: 2026-08-12 16:48:08.528220

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "24b4979b99ef"
down_revision: Union[str, Sequence[str], None] = "90a82456a4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将钱包地址从用户迁移到机构，并限制一个机构只有一个用户。"""

    # 先允许为空，便于将 users 中原有的钱包地址迁移过来。
    op.add_column(
        "organizations",
        sa.Column(
            "wallet_address",
            sa.String(length=42),
            nullable=True,
            comment="机构授权钱包地址，统一以小写保存",
        ),
    )

    # 根据 organization_id 将原用户钱包地址迁移到所属机构。
    op.execute(
        sa.text(
            """
            UPDATE organizations AS organization
            INNER JOIN users AS user
                ON user.organization_id = organization.id
            SET organization.wallet_address = LOWER(user.wallet_address)
            """
        )
    )

    # 数据迁移后，机构钱包地址必须存在且全局唯一。
    op.alter_column(
        "organizations",
        "wallet_address",
        existing_type=sa.String(length=42),
        nullable=False,
        existing_comment="机构授权钱包地址，统一以小写保存",
    )
    op.create_unique_constraint(
        "uq_organizations_wallet_address",
        "organizations",
        ["wallet_address"],
    )

    # 先建立唯一索引，使外键在删除旧索引时仍有索引支持。
    op.create_unique_constraint(
        "uq_users_organization_id",
        "users",
        ["organization_id"],
    )
    op.drop_index("ix_users_organization_id", table_name="users")

    op.drop_column("users", "wallet_address")


def downgrade() -> None:
    """将机构钱包地址迁回用户，恢复原数据库结构。"""

    # 先恢复允许为空的用户钱包字段。
    op.add_column(
        "users",
        sa.Column(
            "wallet_address",
            sa.String(length=42),
            nullable=True,
        ),
    )

    # 从所属机构取回钱包地址，避免降级时丢失已有数据。
    op.execute(
        sa.text(
            """
            UPDATE users AS user
            INNER JOIN organizations AS organization
                ON organization.id = user.organization_id
            SET user.wallet_address = organization.wallet_address
            """
        )
    )

    op.alter_column(
        "users",
        "wallet_address",
        existing_type=sa.String(length=42),
        nullable=False,
    )

    # 先恢复普通索引，再删除唯一约束，保证外键始终有索引支持。
    op.create_index(
        "ix_users_organization_id",
        "users",
        ["organization_id"],
        unique=False,
    )
    op.drop_constraint(
        "uq_users_organization_id",
        "users",
        type_="unique",
    )

    # 恢复原来的用户钱包唯一索引。
    op.create_index(
        "wallet_address",
        "users",
        ["wallet_address"],
        unique=True,
    )

    op.drop_constraint(
        "uq_organizations_wallet_address",
        "organizations",
        type_="unique",
    )
    op.drop_column("organizations", "wallet_address")
