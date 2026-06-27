"""add opens_at and deadline to interview

Revision ID: f7e8d9c0b1a2
Revises: d8bdee2aaf77
Create Date: 2026-06-27 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7e8d9c0b1a2'
down_revision: Union[str, None] = 'd8bdee2aaf77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('interviews', sa.Column('opens_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('interviews', sa.Column('deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('interviews', 'deadline')
    op.drop_column('interviews', 'opens_at')
