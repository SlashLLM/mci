"""Add job order match weight overrides.

Revision ID: 017
Revises: 016
Create Date: 2026-04-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_orders", sa.Column("match_weight_overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_orders", "match_weight_overrides")
