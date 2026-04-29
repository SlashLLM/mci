"""Add automatic dispatch configuration and shift dispatch tasks.

Revision ID: 022
Revises: 021
Create Date: 2026-04-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    columns = inspector.get_columns(table_name)
    return any(col.get("name") == column_name for col in columns)


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    automatic_dispatch_mode_enum = sa.Enum(
        "fcfs",
        "performance_priority",
        "preferred_priority",
        name="automaticdispatchmode",
    )
    dispatch_task_status_enum = sa.Enum(
        "pending",
        "completed",
        "cancelled",
        name="dispatchtaskstatus",
    )
    automatic_dispatch_mode_enum.create(bind, checkfirst=True)
    dispatch_task_status_enum.create(bind, checkfirst=True)

    if not _column_exists(inspector, "job_orders", "automatic_dispatch_enabled"):
        op.add_column(
            "job_orders",
            sa.Column("automatic_dispatch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _column_exists(inspector, "job_orders", "automatic_dispatch_mode"):
        op.add_column(
            "job_orders",
            sa.Column(
                "automatic_dispatch_mode",
                automatic_dispatch_mode_enum,
                nullable=False,
                server_default="fcfs",
            ),
        )
    if not _column_exists(inspector, "job_orders", "automatic_dispatch_min_score"):
        op.add_column("job_orders", sa.Column("automatic_dispatch_min_score", sa.Float(), nullable=True))
    if not _column_exists(inspector, "job_orders", "automatic_dispatch_top_percent"):
        op.add_column("job_orders", sa.Column("automatic_dispatch_top_percent", sa.Integer(), nullable=True))
    if not _column_exists(inspector, "job_orders", "automatic_dispatch_priority_window_minutes"):
        op.add_column(
            "job_orders",
            sa.Column("automatic_dispatch_priority_window_minutes", sa.Integer(), nullable=True),
        )

    if not _table_exists(inspector, "shift_dispatch_tasks"):
        op.create_table(
            "shift_dispatch_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("shift_id", sa.Integer(), nullable=False),
            sa.Column("job_order_id", sa.Integer(), nullable=False),
            sa.Column("phase", sa.String(length=32), nullable=False, server_default="performance_phase_2"),
            sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "status",
                dispatch_task_status_enum,
                nullable=False,
                server_default="pending",
            ),
            sa.Column("dedupe_key", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["job_order_id"], ["job_orders.id"]),
            sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedupe_key", name="uq_shift_dispatch_tasks_dedupe_key"),
        )
        inspector = sa.inspect(bind)
    if not _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_shift_id"):
        op.create_index("ix_shift_dispatch_tasks_shift_id", "shift_dispatch_tasks", ["shift_id"])
    if not _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_job_order_id"):
        op.create_index("ix_shift_dispatch_tasks_job_order_id", "shift_dispatch_tasks", ["job_order_id"])
    if not _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_status"):
        op.create_index("ix_shift_dispatch_tasks_status", "shift_dispatch_tasks", ["status"])
    if not _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_run_after"):
        op.create_index("ix_shift_dispatch_tasks_run_after", "shift_dispatch_tasks", ["run_after"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    automatic_dispatch_mode_enum = sa.Enum(
        "fcfs",
        "performance_priority",
        "preferred_priority",
        name="automaticdispatchmode",
    )
    dispatch_task_status_enum = sa.Enum(
        "pending",
        "completed",
        "cancelled",
        name="dispatchtaskstatus",
    )

    if _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_run_after"):
        op.drop_index("ix_shift_dispatch_tasks_run_after", table_name="shift_dispatch_tasks")
    if _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_status"):
        op.drop_index("ix_shift_dispatch_tasks_status", table_name="shift_dispatch_tasks")
    if _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_job_order_id"):
        op.drop_index("ix_shift_dispatch_tasks_job_order_id", table_name="shift_dispatch_tasks")
    if _index_exists(inspector, "shift_dispatch_tasks", "ix_shift_dispatch_tasks_shift_id"):
        op.drop_index("ix_shift_dispatch_tasks_shift_id", table_name="shift_dispatch_tasks")
    if _table_exists(inspector, "shift_dispatch_tasks"):
        op.drop_table("shift_dispatch_tasks")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "job_orders", "automatic_dispatch_priority_window_minutes"):
        op.drop_column("job_orders", "automatic_dispatch_priority_window_minutes")
    if _column_exists(inspector, "job_orders", "automatic_dispatch_top_percent"):
        op.drop_column("job_orders", "automatic_dispatch_top_percent")
    if _column_exists(inspector, "job_orders", "automatic_dispatch_min_score"):
        op.drop_column("job_orders", "automatic_dispatch_min_score")
    if _column_exists(inspector, "job_orders", "automatic_dispatch_mode"):
        op.drop_column("job_orders", "automatic_dispatch_mode")
    if _column_exists(inspector, "job_orders", "automatic_dispatch_enabled"):
        op.drop_column("job_orders", "automatic_dispatch_enabled")
    dispatch_task_status_enum.drop(bind, checkfirst=True)
    automatic_dispatch_mode_enum.drop(bind, checkfirst=True)
