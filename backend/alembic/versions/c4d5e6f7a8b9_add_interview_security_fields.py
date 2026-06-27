"""add interview security fields (pin, integrity, response_time, paste)

Revision ID: c4d5e6f7a8b9
Revises: f7e8d9c0b1a2
Create Date: 2026-06-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'f7e8d9c0b1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('interviews', sa.Column('access_pin', sa.String(length=12), nullable=True))
    op.add_column('interviews', sa.Column('integrity', sa.Text(), nullable=True))
    op.add_column('interview_answers', sa.Column('response_time', sa.Float(), nullable=True))
    op.add_column('interview_answers', sa.Column('paste_detected', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('interview_answers', 'paste_detected')
    op.drop_column('interview_answers', 'response_time')
    op.drop_column('interviews', 'integrity')
    op.drop_column('interviews', 'access_pin')
