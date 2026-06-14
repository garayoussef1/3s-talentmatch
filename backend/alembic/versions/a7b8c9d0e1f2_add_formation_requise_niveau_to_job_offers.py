"""add formation_requise_niveau to job_offers

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_offers', sa.Column('formation_requise_niveau', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('job_offers', 'formation_requise_niveau')
