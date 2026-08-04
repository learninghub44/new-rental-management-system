from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceCreate(BaseModel):
    """Manual invoice, set by admin, for one tenant/lease."""
    tenant_id: str
    lease_id: Optional[str] = None
    billing_period_start: date
    billing_period_end: date
    due_date: date
    rent: Decimal = Field(default=Decimal("0"), ge=0)
    water: Decimal = Field(default=Decimal("0"), ge=0)
    electricity: Decimal = Field(default=Decimal("0"), ge=0)
    service_charges: Decimal = Field(default=Decimal("0"), ge=0)
    penalties: Decimal = Field(default=Decimal("0"), ge=0)
    discounts: Decimal = Field(default=Decimal("0"), ge=0)
    notes: Optional[str] = None


class InvoiceAdjust(BaseModel):
    """Admin-only tweak to an existing invoice's charges."""
    penalties: Optional[Decimal] = Field(default=None, ge=0)
    discounts: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None


class MonthlyGenerateRequest(BaseModel):
    """Kick off recurring monthly billing for all active leases."""
    billing_period_start: date
    billing_period_end: date
    due_date: date
    water: Decimal = Field(default=Decimal("0"), ge=0)
    electricity: Decimal = Field(default=Decimal("0"), ge=0)
    service_charges: Decimal = Field(default=Decimal("0"), ge=0)
