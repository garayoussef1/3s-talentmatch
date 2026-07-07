"""add access_token to assessment_sessions

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-28 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_sessions', sa.Column('access_token', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_assessment_sessions_access_token'), 'assessment_sessions', ['access_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_assessment_sessions_access_token'), table_name='assessment_sessions')
    op.drop_column('assessment_sessions', 'access_token')
