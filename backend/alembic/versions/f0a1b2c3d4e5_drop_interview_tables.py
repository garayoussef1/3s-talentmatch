"""drop interview tables (module Groq supprimé — API externe interdite)

Le module entretien conversationnel reposait sur Groq (API cloud), interdit
par la politique de confidentialité de l'entreprise. Il est remplacé par le
module d'évaluation 100% local (assessment_*).

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'e9f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interview_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS interview_answers CASCADE")
    op.execute("DROP TABLE IF EXISTS interview_questions CASCADE")
    op.execute("DROP TABLE IF EXISTS interviews CASCADE")
    sa.Enum(name='interviewstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='interviewphase').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='recommendation').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Suppression volontaire et définitive (module retiré) — pas de retour arrière.
    pass
