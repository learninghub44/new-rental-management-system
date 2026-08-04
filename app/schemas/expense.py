from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ExpenseCategory


class ExpenseCreate(BaseModel):
    property_id: str
    category: ExpenseCategory
    description: str = Field(min_length=2)
    amount: Decimal = Field(gt=0)
    expense_date: date
    attachment_url: Optional[str] = None


class ExpenseUpdate(BaseModel):
    category: Optional[ExpenseCategory] = None
    description: Optional[str] = Field(default=None, min_length=2)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    expense_date: Optional[date] = None
    attachment_url: Optional[str] = None
