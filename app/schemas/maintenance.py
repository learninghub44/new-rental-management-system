from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import MaintenancePriority, MaintenanceStatus


class MaintenanceCreate(BaseModel):
    """Tenant-submitted maintenance request against their current unit."""
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    image_url: Optional[str] = None


class MaintenanceUpdate(BaseModel):
    """Admin/caretaker triage and resolution."""
    status: Optional[MaintenanceStatus] = None
    priority: Optional[MaintenancePriority] = None
    assigned_to_user_id: Optional[str] = None
    resolution_notes: Optional[str] = None
