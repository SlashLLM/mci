"""add absent_after_grace_ta_notified_at to attendance_records

Revision ID: 008
Revises: 007
Create Date: 2026-04-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("attendance_records")}
    if "absent_after_grace_ta_notified_at" not in cols:
        op.add_column(
            "attendance_records",
            sa.Column("absent_after_grace_ta_notified_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("attendance_records")}
    if "absent_after_grace_ta_notified_at" in cols:
        op.drop_column("attendance_records", "absent_after_grace_ta_notified_at")
