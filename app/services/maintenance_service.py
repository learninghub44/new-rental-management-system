import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.maintenance import MaintenanceRequest
from app.models.tenant import Tenant
from app.models.enums import MaintenanceStatus
from app.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate


class MaintenanceServiceError(Exception):
    pass


def create_request(db: Session, tenant: Tenant, data: MaintenanceCreate) -> MaintenanceRequest:
    if not tenant.unit_id:
        raise MaintenanceServiceError("You don't currently have an assigned unit")

    request = MaintenanceRequest(
        tenant_id=tenant.id,
        unit_id=tenant.unit_id,
        title=data.title.strip(),
        description=data.description.strip(),
        image_url=data.image_url,
        priority=data.priority,
        status=MaintenanceStatus.SUBMITTED,
    )
    db.add(request)
    db.flush()
    return request


def update_request(db: Session, request_id: uuid.UUID, data: MaintenanceUpdate) -> MaintenanceRequest:
    request = db.get(MaintenanceRequest, request_id)
    if not request:
        raise MaintenanceServiceError("Maintenance request not found")

    if data.status:
        request.status = data.status
    if data.priority:
        request.priority = data.priority
    if data.assigned_to_user_id is not None:
        request.assigned_to_user_id = uuid.UUID(data.assigned_to_user_id) if data.assigned_to_user_id else None
    if data.resolution_notes is not None:
        request.resolution_notes = data.resolution_notes

    db.add(request)
    db.flush()
    return request


def list_requests(
    db: Session, tenant_id: Optional[uuid.UUID] = None, status_filter: Optional[MaintenanceStatus] = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[MaintenanceRequest], int]:
    query = db.query(MaintenanceRequest)
    if tenant_id:
        query = query.filter(MaintenanceRequest.tenant_id == tenant_id)
    if status_filter:
        query = query.filter(MaintenanceRequest.status == status_filter)

    total = query.count()
    items = query.order_by(MaintenanceRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
