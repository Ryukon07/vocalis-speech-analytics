"""Persist local transcription jobs."""

from alembic import op
import sqlalchemy as sa

revision = "c10214_transcriptions"
down_revision = "b33555e19b83"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transcriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column(
            "recording_id",
            sa.String(36),
            sa.ForeignKey("recordings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("language", sa.String(40), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("error_summary", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_transcriptions_recording_id", "transcriptions", ["recording_id"]
    )
    op.create_index("ix_transcriptions_status", "transcriptions", ["status"])


def downgrade():
    op.drop_table("transcriptions")
