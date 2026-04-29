"""Add precomputed worker shift recommendations table.

Revision ID: 021
Revises: 020
Create Date: 2026-04-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
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

    if not _table_exists(inspector, "worker_shift_recommendations"):
        op.create_table(
            "worker_shift_recommendations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("worker_profile_id", sa.Integer(), nullable=False),
            sa.Column("shift_id", sa.Integer(), nullable=False),
            sa.Column("score_total", sa.Float(), nullable=False, server_default="0"),
            sa.Column("urgency_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("return_opportunity", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("score_breakdown", sa.JSON(), nullable=False),
            sa.Column("reason_flags", sa.JSON(), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="daily"),
            sa.ForeignKeyConstraint(["worker_profile_id"], ["worker_profiles.id"]),
            sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("worker_profile_id", "shift_id", name="uq_worker_shift_recommendation_worker_shift"),
        )
        inspector = sa.inspect(bind)
    if not _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_worker_profile_id"):
        op.create_index(
            "ix_worker_shift_recommendations_worker_profile_id",
            "worker_shift_recommendations",
            ["worker_profile_id"],
        )
    if not _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_shift_id"):
        op.create_index(
            "ix_worker_shift_recommendations_shift_id",
            "worker_shift_recommendations",
            ["shift_id"],
        )
    if not _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_score_total"):
        op.create_index(
            "ix_worker_shift_recommendations_score_total",
            "worker_shift_recommendations",
            ["score_total"],
        )
    if not _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_computed_at"):
        op.create_index(
            "ix_worker_shift_recommendations_computed_at",
            "worker_shift_recommendations",
            ["computed_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_computed_at"):
        op.drop_index("ix_worker_shift_recommendations_computed_at", table_name="worker_shift_recommendations")
    if _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_score_total"):
        op.drop_index("ix_worker_shift_recommendations_score_total", table_name="worker_shift_recommendations")
    if _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_shift_id"):
        op.drop_index("ix_worker_shift_recommendations_shift_id", table_name="worker_shift_recommendations")
    if _index_exists(inspector, "worker_shift_recommendations", "ix_worker_shift_recommendations_worker_profile_id"):
        op.drop_index("ix_worker_shift_recommendations_worker_profile_id", table_name="worker_shift_recommendations")
    if _table_exists(inspector, "worker_shift_recommendations"):
        op.drop_table("worker_shift_recommendations")
