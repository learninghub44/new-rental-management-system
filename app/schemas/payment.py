from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PaymentMethod
from app.core.phone import normalize_phone


class ManualPaymentCreate(BaseModel):
    """Admin/accountant recording a cash or bank payment."""
    tenant_id: str
    invoice_id: Optional[str] = None
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    reference: Optional[str] = None
    payment_date: date

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: PaymentMethod) -> PaymentMethod:
        if v not in (PaymentMethod.CASH, PaymentMethod.BANK):
            raise ValueError("Manual payments can only be recorded as cash or bank transfer")
        return v


class STKPushRequest(BaseModel):
    """Tenant-initiated M-Pesa payment via PayHero."""
    invoice_id: Optional[str] = None
    amount: Decimal = Field(gt=0)
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)
