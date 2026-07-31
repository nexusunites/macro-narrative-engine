"""Initial account and authentication schema."""
from alembic import op
from mne.database import Base
from mne import models  # noqa: F401
revision="0001_accounts"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
