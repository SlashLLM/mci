"""Job order E2EE chat tables.

Revision ID: 019
Revises: 018
Create Date: 2026-04-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "user_chat_identities"):
        op.create_table(
            "user_chat_identities",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("x25519_public_key", sa.LargeBinary(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if not _table_exists(inspector, "job_order_chat_key_wrappers"):
        op.create_table(
            "job_order_chat_key_wrappers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("job_order_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("wrapped_key", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_order_id", "user_id", name="uq_job_order_chat_wrap_user"),
        )
        inspector = sa.inspect(bind)
    if not _index_exists(inspector, "job_order_chat_key_wrappers", "ix_job_order_chat_wrappers_job"):
        op.create_index("ix_job_order_chat_wrappers_job", "job_order_chat_key_wrappers", ["job_order_id"])
    if not _index_exists(inspector, "job_order_chat_key_wrappers", "ix_job_order_chat_wrappers_user"):
        op.create_index("ix_job_order_chat_wrappers_user", "job_order_chat_key_wrappers", ["user_id"])

    if not _table_exists(inspector, "job_order_chat_messages"):
        op.create_table(
            "job_order_chat_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("job_order_id", sa.Integer(), nullable=False),
            sa.Column("sender_user_id", sa.Integer(), nullable=False),
            sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
            sa.Column("iv", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    if not _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_job"):
        op.create_index("ix_job_order_chat_msg_job", "job_order_chat_messages", ["job_order_id"])
    if not _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_sender"):
        op.create_index("ix_job_order_chat_msg_sender", "job_order_chat_messages", ["sender_user_id"])
    if not _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_job_created"):
        op.create_index(
            "ix_job_order_chat_msg_job_created",
            "job_order_chat_messages",
            ["job_order_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_job_created"):
        op.drop_index("ix_job_order_chat_msg_job_created", table_name="job_order_chat_messages")
    if _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_sender"):
        op.drop_index("ix_job_order_chat_msg_sender", table_name="job_order_chat_messages")
    if _index_exists(inspector, "job_order_chat_messages", "ix_job_order_chat_msg_job"):
        op.drop_index("ix_job_order_chat_msg_job", table_name="job_order_chat_messages")
    if _table_exists(inspector, "job_order_chat_messages"):
        op.drop_table("job_order_chat_messages")

    inspector = sa.inspect(bind)
    if _index_exists(inspector, "job_order_chat_key_wrappers", "ix_job_order_chat_wrappers_user"):
        op.drop_index("ix_job_order_chat_wrappers_user", table_name="job_order_chat_key_wrappers")
    if _index_exists(inspector, "job_order_chat_key_wrappers", "ix_job_order_chat_wrappers_job"):
        op.drop_index("ix_job_order_chat_wrappers_job", table_name="job_order_chat_key_wrappers")
    if _table_exists(inspector, "job_order_chat_key_wrappers"):
        op.drop_table("job_order_chat_key_wrappers")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "user_chat_identities"):
        op.drop_table("user_chat_identities")
