"""add entreprise and experience_requise to job_offers

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_offers', sa.Column('entreprise', sa.String(255), nullable=True))
    op.add_column('job_offers', sa.Column('experience_requise', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('job_offers', 'experience_requise')
    op.drop_column('job_offers', 'entreprise')
