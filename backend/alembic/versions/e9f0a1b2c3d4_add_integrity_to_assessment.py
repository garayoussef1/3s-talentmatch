"""add integrity to assessment_sessions

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_sessions', sa.Column('integrity', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('assessment_sessions', 'integrity')
