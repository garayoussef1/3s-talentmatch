import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.access_log import AccessLog
from app.models.user import User

logger = logging.getLogger(__name__)

# Actions RGPD suivies
VIEW_CANDIDATE    = "VIEW_CANDIDATE"
DOWNLOAD_CV       = "DOWNLOAD_CV"
DELETE_CANDIDATE  = "DELETE_CANDIDATE"
MATCH_LAUNCHED    = "MATCH_LAUNCHED"
STATUS_CHANGED    = "STATUS_CHANGED"
ANONYMIZE_CANDIDATE = "ANONYMIZE_CANDIDATE"
UPLOAD_CV         = "UPLOAD_CV"


def log_access(
    db: Session,
    action: str,
    current_user: Optional[User] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    try:
        entry = AccessLog(
            user_id=current_user.id if current_user else None,
            user_email=current_user.email if current_user else None,
            user_role=current_user.role.value if current_user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.warning(f"[access_log] Échec journalisation ({action}): {e}")
