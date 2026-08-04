import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.property import Property, Unit
from app.models.enums import PropertyStatus
from app.schemas.property import PropertyCreate, PropertyUpdate


class PropertyServiceError(Exception):
    pass


def list_properties(
    db: Session, search: Optional[str] = None, status_filter: Optional[PropertyStatus] = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[Property], int]:
    query = db.query(Property)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Property.name.ilike(like), Property.location.ilike(like)))
    if status_filter:
        query = query.filter(Property.status == status_filter)

    total = query.count()
    items = query.order_by(Property.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_property_with_unit_counts(db: Session, property_id: uuid.UUID) -> Optional[dict]:
    prop = db.get(Property, property_id)
    if not prop:
        return None
    units = db.query(Unit).filter(Unit.property_id == property_id).order_by(Unit.unit_number).all()
    occupied = sum(1 for u in units if u.status.value == "occupied")
    return {"property": prop, "units": units, "total_units": len(units), "occupied_units": occupied}


def create_property(db: Session, data: PropertyCreate, image_url: Optional[str] = None) -> Property:
    prop = Property(
        name=data.name.strip(),
        location=data.location.strip(),
        description=data.description,
        manager_id=data.manager_id,
        image_url=image_url,
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop)
    db.flush()
    return prop


def update_property(db: Session, property_id: uuid.UUID, data: PropertyUpdate, image_url: Optional[str] = None) -> Property:
    prop = db.get(Property, property_id)
    if not prop:
        raise PropertyServiceError("Property not found")

    if data.name:
        prop.name = data.name.strip()
    if data.location:
        prop.location = data.location.strip()
    if data.description is not None:
        prop.description = data.description
    if data.manager_id is not None:
        prop.manager_id = data.manager_id
    if data.status:
        prop.status = data.status
    if image_url:
        prop.image_url = image_url

    db.add(prop)
    db.flush()
    return prop


def archive_property(db: Session, property_id: uuid.UUID) -> Property:
    prop = db.get(Property, property_id)
    if not prop:
        raise PropertyServiceError("Property not found")
    prop.status = PropertyStatus.INACTIVE
    db.add(prop)
    db.flush()
    return prop
