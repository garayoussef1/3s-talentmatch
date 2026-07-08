"""add job_offer_id to question tables (pool per offer)

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-06-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assessment_questions',
                  sa.Column('job_offer_id', UUID(as_uuid=True),
                            sa.ForeignKey('job_offers.id', ondelete='CASCADE'), nullable=True))
    op.create_index('ix_assessment_questions_job_offer_id', 'assessment_questions', ['job_offer_id'])
    op.add_column('open_questions',
                  sa.Column('job_offer_id', UUID(as_uuid=True),
                            sa.ForeignKey('job_offers.id', ondelete='CASCADE'), nullable=True))
    op.create_index('ix_open_questions_job_offer_id', 'open_questions', ['job_offer_id'])


def downgrade() -> None:
    op.drop_index('ix_open_questions_job_offer_id', table_name='open_questions')
    op.drop_column('open_questions', 'job_offer_id')
    op.drop_index('ix_assessment_questions_job_offer_id', table_name='assessment_questions')
    op.drop_column('assessment_questions', 'job_offer_id')
