"""add rejected to assignmentstatus enum (PostgreSQL)

Revision ID: 005
Revises: 004
Create Date: 2026-03-25

SQLite stores enum values as plain strings from SQLAlchemy — no schema change needed.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # SQLAlchemy default PostgreSQL enum name for AssignmentStatus
        op.execute("ALTER TYPE assignmentstatus ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely; no-op
    pass
