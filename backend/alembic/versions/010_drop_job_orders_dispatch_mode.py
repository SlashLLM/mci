"""drop job_orders.dispatch_mode (unused)

Revision ID: 010
Revises: 009
Create Date: 2026-04-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("job_orders")}
    if "dispatch_mode" in cols:
        op.drop_column("job_orders", "dispatch_mode")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("job_orders")}
    if "dispatch_mode" not in cols:
        op.add_column(
            "job_orders",
            sa.Column(
                "dispatch_mode",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'offers'"),
            ),
        )
