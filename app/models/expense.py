import uuid
from datetime import date
from typing import Optional

from sqlalchemy import String, Text, Date, Numeric, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import ExpenseCategory


class Expense(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "expenses"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[ExpenseCategory] = mapped_column(SAEnum(ExpenseCategory, name="expense_category"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    property: Mapped["Property"] = relationship(back_populates="expenses")

    def __repr__(self) -> str:
        return f"<Expense {self.category} {self.amount}>"
