"""add applied to assignmentstatus enum (PostgreSQL)

Revision ID: 007
Revises: 006
Create Date: 2026-03-25

SQLite stores enum values as plain strings from SQLAlchemy — no schema change needed.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE assignmentstatus ADD VALUE IF NOT EXISTS 'applied'")


def downgrade() -> None:
    pass
