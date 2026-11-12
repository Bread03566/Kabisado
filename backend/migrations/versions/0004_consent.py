"""Gemini consent: user flags, hash-chained consent log, AI usage counter

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("age_band", sa.String(10), nullable=True))
        batch.add_column(sa.Column("gemini_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("consent_policy_version", sa.String(10), nullable=True))
    op.create_table(
        "consent_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(10), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_consent_log_id", "consent_log", ["id"])
    op.create_index("ix_consent_log_user_id", "consent_log", ["user_id"])
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("feature", sa.String(20), nullable=False),
        sa.Column("engine", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_usage_id", "ai_usage", ["id"])
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_usage")
    op.drop_table("consent_log")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("consent_policy_version")
        batch.drop_column("gemini_consent")
        batch.drop_column("age_band")
