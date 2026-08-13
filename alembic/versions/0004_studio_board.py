"""Account-owned Studio board."""

from alembic import op
import sqlalchemy as sa

revision = "0004_studio_board"
down_revision = "0003_saved_stories"
branch_labels = None
depends_on = None


def upgrade():
    if "studio_boards" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "studio_boards",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    if "studio_boards" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("studio_boards")
