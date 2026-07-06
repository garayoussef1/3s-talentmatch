"""add assessment tables (reality gap score)

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-06-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Banque QCM (Module 1)
    op.create_table(
        'assessment_questions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domaine', sa.String(length=80), nullable=False),
        sa.Column('competence_esco', sa.String(length=150), nullable=False),
        sa.Column('difficulte', sa.Integer(), nullable=False),
        sa.Column('discrimination', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('bonne_reponse', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_assessment_questions_domaine', 'assessment_questions', ['domaine'])
    op.create_index('ix_assessment_questions_competence_esco', 'assessment_questions', ['competence_esco'])

    # Sessions de test (Module 1)
    op.create_table(
        'assessment_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', UUID(as_uuid=True), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_offer_id', UUID(as_uuid=True), sa.ForeignKey('job_offers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('domaine', sa.String(length=80), nullable=False),
        sa.Column('status', sa.Enum('in_progress', 'completed', 'abandoned', name='assessmentstatus', create_constraint=False), nullable=False, server_default='in_progress'),
        sa.Column('theta', sa.Float(), nullable=True),
        sa.Column('administered', sa.JSON(), nullable=True),
        sa.Column('competence_scores', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_assessment_sessions_candidate_id', 'assessment_sessions', ['candidate_id'])

    # Questions ouvertes (Module 2)
    op.create_table(
        'open_questions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domaine', sa.String(length=80), nullable=False),
        sa.Column('competence_esco', sa.String(length=150), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('ref_expert', sa.Text(), nullable=False),
        sa.Column('ref_correct', sa.Text(), nullable=False),
        sa.Column('ref_faible', sa.Text(), nullable=False),
        sa.Column('emb_expert', sa.JSON(), nullable=True),
        sa.Column('emb_correct', sa.JSON(), nullable=True),
        sa.Column('emb_faible', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_open_questions_domaine', 'open_questions', ['domaine'])

    # Résultats Reality Gap (Module 3)
    op.create_table(
        'reality_gap_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', UUID(as_uuid=True), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_offer_id', UUID(as_uuid=True), sa.ForeignKey('job_offers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('assessment_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reality_gap_score', sa.Float(), nullable=False),
        sa.Column('fiabilite_cv', sa.Float(), nullable=False),
        sa.Column('score_final_ajuste', sa.Float(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('niveau_label', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_reality_gap_results_candidate_id', 'reality_gap_results', ['candidate_id'])
    op.create_index('ix_reality_gap_results_job_offer_id', 'reality_gap_results', ['job_offer_id'])


def downgrade() -> None:
    op.drop_table('reality_gap_results')
    op.drop_table('open_questions')
    op.drop_table('assessment_sessions')
    op.drop_table('assessment_questions')
    sa.Enum(name='assessmentstatus').drop(op.get_bind(), checkfirst=True)
