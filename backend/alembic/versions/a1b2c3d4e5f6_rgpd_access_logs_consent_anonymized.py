"""rgpd: access_logs table + consent + anonymized fields on candidates

Revision ID: a1b2c3d4e5f6
Revises: 6c59815ab5f0
Create Date: 2026-04-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6c59815ab5f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Table access_logs ────────────────────────────────────────────────────
    op.create_table(
        'access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('detail', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_access_logs_user_id', 'access_logs', ['user_id'])
    op.create_index('ix_access_logs_action', 'access_logs', ['action'])
    op.create_index('ix_access_logs_created_at', 'access_logs', ['created_at'])

    # ── Champs RGPD sur la table candidates ──────────────────────────────────
    op.add_column('candidates', sa.Column('information_acknowledged', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('candidates', sa.Column('information_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('candidates', sa.Column('anonymized', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('candidates', 'anonymized')
    op.drop_column('candidates', 'information_date')
    op.drop_column('candidates', 'information_acknowledged')
    op.drop_index('ix_access_logs_created_at', table_name='access_logs')
    op.drop_index('ix_access_logs_action', table_name='access_logs')
    op.drop_index('ix_access_logs_user_id', table_name='access_logs')
    op.drop_table('access_logs')
