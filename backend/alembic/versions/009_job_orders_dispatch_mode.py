"""placeholder revision (dispatch_mode not used; see 010)

Revision ID: 009
Revises: 008
Create Date: 2026-04-02

Previously added job_orders.dispatch_mode; that column is not used. Migration 010
drops it if present. This revision remains a no-op for linear history.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
