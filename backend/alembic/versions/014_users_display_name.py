"""Add users.display_name for TA/staff display name.

Revision ID: 014
Revises: 013
Create Date: 2026-04-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "display_name" not in cols:
        op.add_column("users", sa.Column("display_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "display_name" in cols:
        op.drop_column("users", "display_name")
