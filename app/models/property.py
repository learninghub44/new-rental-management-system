import uuid
from typing import Optional

from sqlalchemy import String, Text, Numeric, Integer, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import PropertyStatus, UnitStatus, UnitType


class Property(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "properties"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[PropertyStatus] = mapped_column(
        SAEnum(PropertyStatus, name="property_status"), nullable=False, default=PropertyStatus.ACTIVE
    )

    manager: Mapped[Optional["User"]] = relationship(back_populates="managed_properties", foreign_keys=[manager_id])
    units: Mapped[list["Unit"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="property")

    def __repr__(self) -> str:
        return f"<Property {self.name}>"


class Unit(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "units"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    floor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType, name="unit_type"), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monthly_rent: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[UnitStatus] = mapped_column(
        SAEnum(UnitStatus, name="unit_status"), nullable=False, default=UnitStatus.AVAILABLE
    )

    property: Mapped["Property"] = relationship(back_populates="units")
    leases: Mapped[list["Lease"]] = relationship(back_populates="unit")

    __table_args__ = (
        # A unit number must be unique within a property, not globally.
        UniqueConstraint("property_id", "unit_number", name="uq_unit_number_per_property"),
    )

    def __repr__(self) -> str:
        return f"<Unit {self.unit_number} @ {self.property_id}>"
