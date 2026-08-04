import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.phone import default_password_from_phone
from app.models.tenant import Tenant
from app.models.user import User
from app.models.enums import TenantStatus, UserRole, UserStatus
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantServiceError(Exception):
    pass


def list_tenants(
    db: Session, search: Optional[str] = None, status_filter: Optional[TenantStatus] = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[Tenant], int]:
    query = db.query(Tenant)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Tenant.full_name.ilike(like), Tenant.phone.ilike(like), Tenant.national_id.ilike(like)))
    if status_filter:
        query = query.filter(Tenant.status == status_filter)

    total = query.count()
    items = query.order_by(Tenant.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def create_tenant(db: Session, data: TenantCreate) -> tuple[Tenant, Optional[str]]:
    """
    Creates a Tenant profile. If create_login is True (default) and an email
    is provided, also provisions a linked User login account — following the
    same rule as staff accounts: no self sign-up, default password is the
    last 6 digits of the phone number.
    Returns (tenant, default_password_or_none).
    """
    existing = db.query(Tenant).filter(
        or_(Tenant.phone == data.phone, Tenant.national_id == data.national_id)
    ).first()
    if existing:
        field = "phone" if existing.phone == data.phone else "national ID"
        raise TenantServiceError(f"A tenant with this {field} already exists")

    tenant = Tenant(
        full_name=data.full_name.strip(),
        phone=data.phone,
        email=data.email,
        national_id=data.national_id.strip(),
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=data.emergency_contact_phone,
        status=TenantStatus.ACTIVE,
    )
    db.add(tenant)
    db.flush()

    default_password = None
    if data.create_login and data.email:
        user_exists = db.query(User).filter(or_(User.email == data.email.lower(), User.phone == data.phone)).first()
        if not user_exists:
            default_password = default_password_from_phone(data.phone)
            user = User(
                name=tenant.full_name,
                email=data.email.lower().strip(),
                phone=data.phone,
                password_hash=hash_password(default_password),
                role=UserRole.TENANT,
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            db.flush()
            tenant.user_id = user.id
            db.add(tenant)
            db.flush()

    return tenant, default_password


def update_tenant(db: Session, tenant_id: uuid.UUID, data: TenantUpdate) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise TenantServiceError("Tenant not found")

    if data.phone and data.phone != tenant.phone:
        if db.query(Tenant).filter(Tenant.phone == data.phone, Tenant.id != tenant_id).first():
            raise TenantServiceError("A tenant with this phone already exists")
        tenant.phone = data.phone
    if data.national_id and data.national_id != tenant.national_id:
        if db.query(Tenant).filter(Tenant.national_id == data.national_id, Tenant.id != tenant_id).first():
            raise TenantServiceError("A tenant with this national ID already exists")
        tenant.national_id = data.national_id.strip()

    if data.full_name:
        tenant.full_name = data.full_name.strip()
    if data.email is not None:
        tenant.email = data.email
    if data.emergency_contact_name is not None:
        tenant.emergency_contact_name = data.emergency_contact_name
    if data.emergency_contact_phone is not None:
        tenant.emergency_contact_phone = data.emergency_contact_phone
    if data.status:
        tenant.status = data.status

    db.add(tenant)
    db.flush()
    return tenant


def move_tenant_out(db: Session, tenant_id: uuid.UUID) -> Tenant:
    """Marks a tenant moved out and frees their current unit."""
    from app.models.property import Unit
    from app.models.enums import UnitStatus

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise TenantServiceError("Tenant not found")

    if tenant.unit_id:
        unit = db.get(Unit, tenant.unit_id)
        if unit:
            unit.status = UnitStatus.AVAILABLE
            db.add(unit)

    tenant.status = TenantStatus.MOVED_OUT
    tenant.unit_id = None
    tenant.property_id = None
    db.add(tenant)
    db.flush()
    return tenant
