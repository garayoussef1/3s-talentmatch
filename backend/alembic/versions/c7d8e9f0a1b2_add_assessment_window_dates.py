"""add opens_at and deadline to assessment_sessions

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-07-07 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_sessions', sa.Column('opens_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assessment_sessions', sa.Column('deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('assessment_sessions', 'deadline')
    op.drop_column('assessment_sessions', 'opens_at')
