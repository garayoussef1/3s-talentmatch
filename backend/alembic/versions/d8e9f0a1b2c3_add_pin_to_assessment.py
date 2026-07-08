"""add access_pin to assessment_sessions

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-07-07 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_sessions', sa.Column('access_pin', sa.String(length=12), nullable=True))


def downgrade() -> None:
    op.drop_column('assessment_sessions', 'access_pin')
