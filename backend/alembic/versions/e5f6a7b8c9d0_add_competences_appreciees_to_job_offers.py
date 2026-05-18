"""add competences_appreciees to job_offers

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_offers', sa.Column('competences_appreciees', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('job_offers', 'competences_appreciees')
