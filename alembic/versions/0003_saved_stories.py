"""Account-owned saved stories."""

from alembic import op
import sqlalchemy as sa

revision = "0003_saved_stories"
down_revision = "0002_entitlements_usage"
branch_labels = None
depends_on = None


def upgrade():
    if "saved_stories" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "saved_stories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("story_slug", sa.String(120), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", "story_slug"),
    )
    op.create_index("ix_saved_stories_user_id", "saved_stories", ["user_id"])


def downgrade():
    if "saved_stories" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("saved_stories")
