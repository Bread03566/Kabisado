"""system_status heartbeat table (last backup time shown on the admin dashboard)

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_status",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("value", sa.String(100), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_status")
