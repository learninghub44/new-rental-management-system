import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import UnitStatus, UnitType


class UnitCreate(BaseModel):
    property_id: uuid.UUID
    unit_number: str = Field(min_length=1, max_length=50)
    floor: Optional[str] = None
    unit_type: UnitType
    bedrooms: int = Field(default=0, ge=0)
    monthly_rent: Decimal = Field(gt=0)


class UnitUpdate(BaseModel):
    unit_number: Optional[str] = Field(default=None, min_length=1, max_length=50)
    floor: Optional[str] = None
    unit_type: Optional[UnitType] = None
    bedrooms: Optional[int] = Field(default=None, ge=0)
    monthly_rent: Optional[Decimal] = Field(default=None, gt=0)
    status: Optional[UnitStatus] = None
