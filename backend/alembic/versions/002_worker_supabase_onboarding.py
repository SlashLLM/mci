"""worker supabase id, onboarding fields, document storage columns

Revision ID: 002
Revises: 001
Create Date: 2026-03-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _idx_names(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    # 001 uses metadata.create_all(); current models may already include these columns.
    if "supabase_auth_id" not in _cols("users"):
        op.add_column("users", sa.Column("supabase_auth_id", sa.String(length=36), nullable=True))
    if "ix_users_supabase_auth_id" not in _idx_names("users"):
        op.create_index("ix_users_supabase_auth_id", "users", ["supabase_auth_id"], unique=True)

    wp = _cols("worker_profiles")
    if "bank_name" not in wp:
        op.add_column("worker_profiles", sa.Column("bank_name", sa.String(length=255), nullable=True))
    if "work_pass_not_applicable" not in wp:
        op.add_column(
            "worker_profiles",
            sa.Column("work_pass_not_applicable", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "terms_accepted_at" not in wp:
        op.add_column(
            "worker_profiles",
            sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "onboarding_completed_at" not in wp:
        op.add_column(
            "worker_profiles",
            sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        )

    doc = _cols("documents")
    if "storage_bucket" not in doc:
        op.add_column("documents", sa.Column("storage_bucket", sa.String(length=128), nullable=True))
    if "storage_object_path" not in doc:
        op.add_column("documents", sa.Column("storage_object_path", sa.String(length=1024), nullable=True))

    fp = next((c for c in sa.inspect(op.get_bind()).get_columns("documents") if c["name"] == "file_path"), None)
    if fp is not None and fp.get("nullable") is False:
        op.alter_column("documents", "file_path", existing_type=sa.String(length=512), nullable=True)


def downgrade() -> None:
    op.alter_column("documents", "file_path", existing_type=sa.String(length=512), nullable=False)
    op.drop_column("documents", "storage_object_path")
    op.drop_column("documents", "storage_bucket")
    op.drop_column("worker_profiles", "onboarding_completed_at")
    op.drop_column("worker_profiles", "terms_accepted_at")
    op.drop_column("worker_profiles", "work_pass_not_applicable")
    op.drop_column("worker_profiles", "bank_name")
    op.drop_index("ix_users_supabase_auth_id", table_name="users")
    op.drop_column("users", "supabase_auth_id")
