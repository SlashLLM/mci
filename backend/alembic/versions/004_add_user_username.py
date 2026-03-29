"""add username to users

Revision ID: 004
Revises: 003
Create Date: 2026-03-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "username" not in user_cols:
        op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
        op.create_index("ix_users_username", "users", ["username"], unique=True)
    # If 001 create_all already added username + unique, skip (avoids duplicate index).


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
