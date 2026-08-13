"""Give Studio boards identities and allow multiple theses per account.

Downgrade is intentionally lossy: it retains only each account's most recently
updated thesis board because the Q1 schema permits one row per account.
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0005_studio_boards_multi"
down_revision = "0004_studio_board"
branch_labels = None
depends_on = None


def _new_table(name: str) -> sa.Table:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("user_id", sa.String(36), primary_key=True))
    return sa.Table(
        name,
        metadata,
        sa.Column("board_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    bind = op.get_bind()
    if "studio_boards" not in sa.inspect(bind).get_table_names():
        return
    old = sa.Table("studio_boards", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(sa.select(old.c.user_id, old.c.payload, old.c.updated_at)).mappings().all()
    op.rename_table("studio_boards", "studio_boards_q1")
    table = _new_table("studio_boards")
    table.create(bind)
    if rows:
        bind.execute(table.insert(), [
            {
                "board_id": str(uuid.uuid4()),
                "user_id": row["user_id"],
                "payload": row["payload"],
                "created_at": row["updated_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ])
    op.drop_table("studio_boards_q1")
    op.create_index("ix_studio_boards_user_id", "studio_boards", ["user_id"])


def downgrade():
    bind = op.get_bind()
    if "studio_boards" not in sa.inspect(bind).get_table_names():
        return
    current = sa.Table("studio_boards", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(
        sa.select(current.c.user_id, current.c.payload, current.c.updated_at)
        .order_by(current.c.user_id, current.c.updated_at.desc(), current.c.board_id.desc())
    ).mappings().all()
    newest = {}
    for row in rows:
        newest.setdefault(row["user_id"], row)
    op.rename_table("studio_boards", "studio_boards_q2")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("user_id", sa.String(36), primary_key=True))
    q1 = sa.Table(
        "studio_boards",
        metadata,
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    q1.create(bind)
    if newest:
        bind.execute(q1.insert(), [
            {"user_id": row["user_id"], "payload": row["payload"], "updated_at": row["updated_at"]}
            for row in newest.values()
        ])
    op.drop_table("studio_boards_q2")
