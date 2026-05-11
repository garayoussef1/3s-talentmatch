"""add date_limite to job_offers

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_offers', sa.Column('date_limite', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('job_offers', 'date_limite')
