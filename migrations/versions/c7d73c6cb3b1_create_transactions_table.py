"""create transactions table

Revision ID: c7d73c6cb3b1
Revises: 5fb1cc1d4e85
Create Date: 2026-08-23 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d73c6cb3b1"
down_revision: str | Sequence[str] | None = "5fb1cc1d4e85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_by_organization_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_organization_id", sa.BigInteger(), nullable=False),
        sa.Column("receiver_organization_id", sa.BigInteger(), nullable=False),
        sa.Column("send_asset", sa.String(length=16), nullable=False),
        sa.Column("send_asset_address", sa.String(length=42), nullable=False),
        sa.Column("send_amount", sa.String(length=78), nullable=False),
        sa.Column("receive_asset", sa.String(length=16), nullable=False),
        sa.Column("receive_asset_address", sa.String(length=42), nullable=False),
        sa.Column("receive_amount", sa.String(length=78), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "submitted",
                "settled",
                "failed",
                name="transactionstatus",
                native_enum=False,
                length=32,
            ),
            server_default="submitted",
            nullable=False,
        ),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("window_id", sa.String(length=78), nullable=False),
        sa.Column("trade_id", sa.String(length=78), nullable=False),
        sa.Column("submission_hash", sa.String(length=66), nullable=False),
        sa.Column("submission_block", sa.BigInteger(), nullable=False),
        sa.Column("settlement_hash", sa.String(length=66), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("settled_at", sa.BigInteger(), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sender_organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receiver_organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chain_id",
            "submission_hash",
            name="uq_transactions_chain_submission_hash",
        ),
    )
    op.create_index(
        "ix_transactions_sender_organization_id",
        "transactions",
        ["sender_organization_id"],
    )
    op.create_index(
        "ix_transactions_receiver_organization_id",
        "transactions",
        ["receiver_organization_id"],
    )
    op.create_index("ix_transactions_status", "transactions", ["status"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_receiver_organization_id", table_name="transactions")
    op.drop_index("ix_transactions_sender_organization_id", table_name="transactions")
    op.drop_table("transactions")
