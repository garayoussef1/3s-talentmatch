"""add_auth_fields_to_users

Revision ID: 50b7de3c8c50
Revises: ee370044acc8
Create Date: 2026-03-10 17:31:35.529064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50b7de3c8c50'
down_revision: Union[str, None] = 'ee370044acc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer l'enum PostgreSQL d'abord
    authprovider_enum = sa.Enum('local', 'google', 'linkedin', name='authprovider')
    authprovider_enum.create(op.get_bind(), checkfirst=True)

    # Ajouter le rôle 'candidat' à l'enum userrole existant
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'candidat'")

    op.add_column('users', sa.Column('auth_provider', authprovider_enum, server_default='local', nullable=False))
    op.add_column('users', sa.Column('oauth_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    op.alter_column('users', 'hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.alter_column('users', 'hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'auth_provider')
    sa.Enum(name='authprovider').drop(op.get_bind(), checkfirst=True)
    # ### end Alembic commands ###
