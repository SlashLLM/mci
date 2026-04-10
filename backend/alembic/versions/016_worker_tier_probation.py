"""Add probation worker tier.

Revision ID: 016
Revises: 015
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE workertier ADD VALUE IF NOT EXISTS 'probation'")


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally left as a no-op because it
    # is not safe once rows may already use the value.
    return None
