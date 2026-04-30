"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("output_response", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "guardrail_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("blocked_keyword", sa.Text(), nullable=True),
        sa.Column("violation_type", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("client_ip", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("guardrail_logs")
    op.drop_table("request_logs")
