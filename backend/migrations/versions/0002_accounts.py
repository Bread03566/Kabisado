"""accounts: user credentials/roles, sessions, login attempts

Revision ID: 0002
Revises: 0001
"""
import secrets
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. New columns, nullable so existing rows survive; email is dropped (we do not collect it).
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("display_name", sa.String(60), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.Text(), nullable=True))
        batch.add_column(sa.Column("recovery_hash", sa.Text(), nullable=True))
        batch.add_column(sa.Column("role", sa.String(10), nullable=False, server_default="student"))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("subject_ref", sa.String(32), nullable=True))
        batch.drop_column("email")

    # 2. Backfill existing (legacy client-id) rows. They get no password, so they can never log in.
    conn = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("username", sa.String),
                     sa.column("public_id", sa.String), sa.column("display_name", sa.String),
                     sa.column("subject_ref", sa.String))
    for row in conn.execute(sa.select(users.c.id, users.c.username)).fetchall():
        conn.execute(users.update().where(users.c.id == row.id).values(
            public_id=str(uuid.uuid4()),
            display_name=(row.username or "student")[:60],
            subject_ref=secrets.token_hex(16),
        ))

    # 3. Tighten constraints now that every row has values.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("public_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("display_name", existing_type=sa.String(60), nullable=False)
        batch.alter_column("subject_ref", existing_type=sa.String(32), nullable=False)
        batch.alter_column("username", existing_type=sa.String(100), nullable=False)
        batch.create_index("ix_users_public_id", ["public_id"], unique=True)
        batch.create_unique_constraint("uq_users_subject_ref", ["subject_ref"])
        batch.create_check_constraint("ck_users_role", "role IN ('student', 'admin')")

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("refresh_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by", sa.Integer(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_sessions_id", "sessions", ["id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_family_id", "sessions", ["family_id"])

    op.create_table(
        "login_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("sessions")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
        batch.drop_constraint("uq_users_subject_ref", type_="unique")
        batch.drop_index("ix_users_public_id")
        for col in ("subject_ref", "last_login_at", "is_active", "role", "recovery_hash", "password_hash",
                    "display_name", "public_id"):
            batch.drop_column(col)
        batch.add_column(sa.Column("email", sa.String(255), nullable=True))
