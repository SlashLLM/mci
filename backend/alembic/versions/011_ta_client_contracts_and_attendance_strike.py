"""ta_client_contracts, attendance absence_strike_recorded_at, timesheet status

Revision ID: 011
Revises: 010
Create Date: 2026-04-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# For downgrade only — must match DB type name
tacc_enum = sa.Enum(
    "pending_ta",
    "active",
    "declined",
    "terminated",
    name="taclientcontractstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        tacc_enum.create(bind, checkfirst=True)
        op.execute(
            "ALTER TYPE timesheetstatus ADD VALUE IF NOT EXISTS 'client_payroll_released'"
        )
        # Reuse the type created above; op.create_table must not emit a second CREATE TYPE
        status_col = sa.Column(
            "status",
            postgresql.ENUM(
                "pending_ta",
                "active",
                "declined",
                "terminated",
                name="taclientcontractstatus",
                create_type=False,
            ),
            nullable=False,
        )
    else:
        status_col = sa.Column("status", sa.String(32), nullable=False)

    # Table may already exist if metadata.create_all() ran or a previous upgrade failed mid-way.
    if not insp.has_table("ta_client_contracts"):
        op.create_table(
            "ta_client_contracts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("client_org_id", sa.Integer(), nullable=False),
            sa.Column("ta_user_id", sa.Integer(), nullable=False),
            status_col,
            sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["client_org_id"], ["client_organizations.id"]),
            sa.ForeignKeyConstraint(["ta_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    ix_names = {ix["name"] for ix in sa.inspect(bind).get_indexes("ta_client_contracts")}
    if "ix_ta_client_contracts_client_org_id" not in ix_names:
        op.create_index("ix_ta_client_contracts_client_org_id", "ta_client_contracts", ["client_org_id"])
    if "ix_ta_client_contracts_ta_user_id" not in ix_names:
        op.create_index("ix_ta_client_contracts_ta_user_id", "ta_client_contracts", ["ta_user_id"])
    if "uq_ta_client_contract_one_active_per_org" not in ix_names:
        op.create_index(
            "uq_ta_client_contract_one_active_per_org",
            "ta_client_contracts",
            ["client_org_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )

    # PGInspector has no has_column(); use get_columns (works PostgreSQL + SQLite).
    ar_cols = {c["name"] for c in sa.inspect(bind).get_columns("attendance_records")}
    if "absence_strike_recorded_at" not in ar_cols:
        op.add_column(
            "attendance_records",
            sa.Column("absence_strike_recorded_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("attendance_records", "absence_strike_recorded_at")
    op.drop_index("uq_ta_client_contract_one_active_per_org", table_name="ta_client_contracts")
    op.drop_index("ix_ta_client_contracts_ta_user_id", table_name="ta_client_contracts")
    op.drop_index("ix_ta_client_contracts_client_org_id", table_name="ta_client_contracts")
    op.drop_table("ta_client_contracts")
    if bind.dialect.name == "postgresql":
        tacc_enum.drop(bind, checkfirst=True)
    # timesheetstatus value client_payroll_released: PostgreSQL cannot remove enum values safely
