"""add domaine_metier and niveau_seniorite to job_offers

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_offers', sa.Column('domaine_metier', sa.String(100), nullable=True))
    op.add_column('job_offers', sa.Column('niveau_seniorite', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('job_offers', 'domaine_metier')
    op.drop_column('job_offers', 'niveau_seniorite')
