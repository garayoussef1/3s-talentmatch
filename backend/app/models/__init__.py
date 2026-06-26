# Importer tous les modèles pour qu'Alembic les détecte
from app.models.candidate import Candidate
from app.models.user import User
from app.models.cv_document import CVDocument
from app.models.job_offer import JobOffer
from app.models.match import Match
from app.models.access_log import AccessLog
from app.models.notification import Notification
from app.models.interview import (
    Interview, InterviewQuestion, InterviewAnswer, InterviewReport,
)

__all__ = [
    "Candidate", "User", "CVDocument", "JobOffer", "Match", "AccessLog",
    "Notification",
    "Interview", "InterviewQuestion", "InterviewAnswer", "InterviewReport",
]
