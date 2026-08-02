import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.system import ActivityLog
from app.models.enums import ActivityAction


def log_activity(
    db: Session,
    action: ActivityAction,
    user_id: Optional[uuid.UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    description: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> ActivityLog:
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry
