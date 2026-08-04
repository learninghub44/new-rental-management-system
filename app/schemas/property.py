import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import PropertyStatus


class PropertyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=300)
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    location: Optional[str] = Field(default=None, min_length=2, max_length=300)
    description: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    status: Optional[PropertyStatus] = None
