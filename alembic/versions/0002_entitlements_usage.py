"""Entitlements, audited internal access, and monthly usage."""

from alembic import op
import sqlalchemy as sa

revision = "0002_entitlements_usage"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "internal_full_access" not in user_columns:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("internal_full_access", sa.Boolean(), nullable=False, server_default=sa.false()))
    audit_columns = {column["name"] for column in inspector.get_columns("audit_log")}
    if "details" not in audit_columns:
        with op.batch_alter_table("audit_log") as batch:
            batch.add_column(sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    tables = set(inspector.get_table_names())
    if "usage_records" not in tables:
        op.create_table(
        "usage_records",
        sa.Column("usage_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("consumed >= 0", name="ck_usage_consumed_nonnegative"),
        sa.UniqueConstraint("user_id", "metric", "period_start", name="uq_usage_record_period"),
        )
        op.create_index("ix_usage_records_user_id", "usage_records", ["user_id"])
    if "usage_events" not in tables:
        op.create_table(
        "usage_events",
        sa.Column("event_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("object_reference", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])


def downgrade():
    op.drop_table("usage_events")
    op.drop_table("usage_records")
    with op.batch_alter_table("audit_log") as batch:
        batch.drop_column("details")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("internal_full_access")
