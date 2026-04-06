"""nullable users.phone; unique email when set (worker self-registration)

Revision ID: 012
Revises: 011
Create Date: 2026-04-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "phone",
                existing_type=sa.String(length=32),
                nullable=True,
            )
    else:
        op.alter_column(
            "users",
            "phone",
            existing_type=sa.String(length=32),
            nullable=True,
        )

    if dialect == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower "
            "ON users (lower(email)) WHERE email IS NOT NULL"
        )
    elif dialect == "sqlite":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower "
            "ON users (email) WHERE email IS NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
    elif dialect == "sqlite":
        op.execute("DROP INDEX IF EXISTS uq_users_email_lower")

    if dialect == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "phone",
                existing_type=sa.String(length=32),
                nullable=False,
            )
    else:
        op.alter_column(
            "users",
            "phone",
            existing_type=sa.String(length=32),
            nullable=False,
        )
