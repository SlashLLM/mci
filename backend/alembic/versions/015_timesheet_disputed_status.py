"""Add disputed timesheet status.

Revision ID: 015
Revises: 014
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE timesheetstatus ADD VALUE IF NOT EXISTS 'disputed'")


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally left as a no-op because it
    # is not safe once rows may already use the value.
    return None
