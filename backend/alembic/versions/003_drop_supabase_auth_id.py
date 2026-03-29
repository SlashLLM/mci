"""drop supabase_auth_id from users

Revision ID: 003
Revises: 002
Create Date: 2026-03-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "ix_users_supabase_auth_id" in {ix["name"] for ix in insp.get_indexes("users")}:
        op.drop_index("ix_users_supabase_auth_id", table_name="users")
    if "supabase_auth_id" in {c["name"] for c in insp.get_columns("users")}:
        op.drop_column("users", "supabase_auth_id")


def downgrade() -> None:
    op.add_column("users", sa.Column("supabase_auth_id", sa.String(length=36), nullable=True))
    op.create_index("ix_users_supabase_auth_id", "users", ["supabase_auth_id"], unique=True)
