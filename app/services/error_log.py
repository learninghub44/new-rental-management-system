import logging
import traceback
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.system import ErrorLog

logger = logging.getLogger("rental_app")


def log_error(
    db: Session,
    module: str,
    message: str,
    exc: Optional[BaseException] = None,
    user_id: Optional[uuid.UUID] = None,
) -> ErrorLog:
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else None
    logger.error("[%s] %s", module, message, exc_info=exc is not None)

    entry = ErrorLog(module=module, message=message, stack_trace=stack_trace, user_id=user_id)
    db.add(entry)
    db.flush()
    return entry
