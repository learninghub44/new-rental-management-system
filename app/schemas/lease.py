import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LeaseCreate(BaseModel):
    tenant_id: uuid.UUID
    unit_id: uuid.UUID
    start_date: date
    end_date: Optional[date] = None
    rent_amount: Decimal = Field(gt=0)
    deposit: Decimal = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date and self.end_date <= self.start_date:
            raise ValueError("End date must be after start date")
        return self


class LeaseRenew(BaseModel):
    new_end_date: date
    new_rent_amount: Optional[Decimal] = Field(default=None, gt=0)
