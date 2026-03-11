"""add_user_id_and_candidature_status_to_candidates

Revision ID: 0d5acab76a9e
Revises: 50b7de3c8c50
Create Date: 2026-03-10 17:59:19.697456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d5acab76a9e'
down_revision: Union[str, None] = '50b7de3c8c50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer l'enum PostgreSQL avant de l'utiliser dans la colonne
    candidaturestatus_enum = sa.Enum('en_attente', 'accepte', 'refuse', name='candidaturestatus')
    candidaturestatus_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('candidates', sa.Column('user_id', sa.UUID(), nullable=True))
    op.add_column('candidates', sa.Column(
        'candidature_status',
        candidaturestatus_enum,
        nullable=False,
        server_default='en_attente',
    ))
    op.create_index(op.f('ix_candidates_user_id'), 'candidates', ['user_id'], unique=False)
    op.create_foreign_key('fk_candidates_user_id', 'candidates', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_constraint('fk_candidates_user_id', 'candidates', type_='foreignkey')
    op.drop_index(op.f('ix_candidates_user_id'), table_name='candidates')
    op.drop_column('candidates', 'candidature_status')
    op.drop_column('candidates', 'user_id')
    sa.Enum(name='candidaturestatus').drop(op.get_bind(), checkfirst=True)
    # ### end Alembic commands ###
