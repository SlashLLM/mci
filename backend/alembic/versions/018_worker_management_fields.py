"""Add worker management notes and follow-up flag.

Revision ID: 018
Revises: 017
Create Date: 2026-04-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("worker_profiles")}

    if "internal_notes" not in column_names:
        op.add_column("worker_profiles", sa.Column("internal_notes", sa.Text(), nullable=True))

    if "follow_up_required" not in column_names:
        op.add_column(
            "worker_profiles",
            sa.Column("follow_up_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("worker_profiles", "follow_up_required", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("worker_profiles")}

    if "follow_up_required" in column_names:
        op.drop_column("worker_profiles", "follow_up_required")
    if "internal_notes" in column_names:
        op.drop_column("worker_profiles", "internal_notes")
