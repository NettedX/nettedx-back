"""add trade event index

Revision ID: 5fb1cc1d4e85
Revises: 24b4979b99ef
Create Date: 2026-08-23 00:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5fb1cc1d4e85"
down_revision: Union[str, Sequence[str], None] = "24b4979b99ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blockchain_event_cursors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_address", sa.String(length=42), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("last_synced_block", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chain_id",
            "contract_address",
            "event_name",
            name="uq_blockchain_event_cursor",
        ),
    )
    op.create_table(
        "trade_submitted_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_address", sa.String(length=42), nullable=False),
        sa.Column("block_number", sa.BigInteger(), nullable=False),
        sa.Column("transaction_hash", sa.String(length=66), nullable=False),
        sa.Column("log_index", sa.Integer(), nullable=False),
        sa.Column("window_id", sa.String(length=78), nullable=False),
        sa.Column("trade_id", sa.String(length=78), nullable=False),
        sa.Column("buyer", sa.String(length=42), nullable=False),
        sa.Column("seller", sa.String(length=42), nullable=False),
        sa.Column("cash_amount", sa.String(length=78), nullable=False),
        sa.Column("bond_amount", sa.String(length=78), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chain_id",
            "contract_address",
            "transaction_hash",
            "log_index",
            name="uq_trade_submitted_event_log",
        ),
    )
    op.create_index(
        "ix_trade_submitted_events_block_number",
        "trade_submitted_events",
        ["block_number"],
        unique=False,
    )
    op.create_index(
        "ix_trade_submitted_events_buyer",
        "trade_submitted_events",
        ["buyer"],
        unique=False,
    )
    op.create_index(
        "ix_trade_submitted_events_seller",
        "trade_submitted_events",
        ["seller"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trade_submitted_events_seller", table_name="trade_submitted_events")
    op.drop_index("ix_trade_submitted_events_buyer", table_name="trade_submitted_events")
    op.drop_index("ix_trade_submitted_events_block_number", table_name="trade_submitted_events")
    op.drop_table("trade_submitted_events")
    op.drop_table("blockchain_event_cursors")
