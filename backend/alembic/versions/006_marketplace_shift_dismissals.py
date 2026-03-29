"""marketplace_shift_dismissals table

Revision ID: 006
Revises: 005
Create Date: 2026-03-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table may already exist if metadata.create_all() ran before Alembic reached 006.
    insp = sa.inspect(op.get_bind())
    if insp.has_table("marketplace_shift_dismissals"):
        return
    op.create_table(
        "marketplace_shift_dismissals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("worker_profile_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.ForeignKeyConstraint(["worker_profile_id"], ["worker_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_profile_id", "shift_id", name="uq_marketplace_dismiss_worker_shift"),
    )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("marketplace_shift_dismissals"):
        op.drop_table("marketplace_shift_dismissals")
