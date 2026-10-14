"""Keep source-speech identity separate from individual excerpt recordings."""

from alembic import op
import sqlalchemy as sa

revision = "c10215_source_identity"
down_revision = "c10214_transcriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "contrastive_groups",
        sa.Column("source_id", sa.String(100), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_contrastive_groups_source_id", "contrastive_groups", ["source_id"]
    )


def downgrade():
    op.drop_index("ix_contrastive_groups_source_id", table_name="contrastive_groups")
    op.drop_column("contrastive_groups", "source_id")
