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
    op.add_column("worker_profiles", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column(
        "worker_profiles",
        sa.Column("follow_up_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("worker_profiles", "follow_up_required", server_default=None)


def downgrade() -> None:
    op.drop_column("worker_profiles", "follow_up_required")
    op.drop_column("worker_profiles", "internal_notes")
