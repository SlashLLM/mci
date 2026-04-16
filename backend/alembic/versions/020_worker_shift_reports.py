"""Add worker shift reports table.

Revision ID: 020
Revises: 019
Create Date: 2026-04-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_shift_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shift_assignment_id", sa.Integer(), nullable=False),
        sa.Column("worker_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "under_review", "resolved", name="workerreportstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shift_assignment_id"], ["shift_assignments.id"]),
        sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_assignment_id", "worker_user_id", name="uq_worker_shift_report_assignment_worker"),
    )
    op.create_index("ix_worker_shift_reports_shift_assignment_id", "worker_shift_reports", ["shift_assignment_id"])
    op.create_index("ix_worker_shift_reports_worker_user_id", "worker_shift_reports", ["worker_user_id"])
    op.create_index("ix_worker_shift_reports_status", "worker_shift_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_worker_shift_reports_status", table_name="worker_shift_reports")
    op.drop_index("ix_worker_shift_reports_worker_user_id", table_name="worker_shift_reports")
    op.drop_index("ix_worker_shift_reports_shift_assignment_id", table_name="worker_shift_reports")
    op.drop_table("worker_shift_reports")
    sa.Enum(name="workerreportstatus").drop(op.get_bind(), checkfirst=True)
