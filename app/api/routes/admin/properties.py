import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.property import Property
from app.models.enums import PropertyStatus, UserRole, ActivityAction
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.services.property_service import (
    list_properties, get_property_with_unit_counts, create_property, update_property,
    archive_property, PropertyServiceError,
)
from app.services.upload_service import save_upload, UploadError
from app.services.activity_log import log_activity

router = APIRouter(prefix="/admin/properties", tags=["admin-properties"])


@router.get("")
def properties_list(
    request: Request, search: str = "", status_filter: str = "", page: int = 1,
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    status_enum = PropertyStatus(status_filter) if status_filter else None
    properties, total = list_properties(db, search=search or None, status_filter=status_enum, page=page)
    return templates.TemplateResponse(
        "admin/properties/list.html",
        {"request": request, "user": user, "properties": properties, "total": total,
         "search": search, "status_filter": status_filter, "statuses": list(PropertyStatus)},
    )


@router.get("/new")
def property_new_form(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    managers = db.query(User).filter(User.role.in_([UserRole.CARETAKER, UserRole.ADMIN])).order_by(User.name).all()
    return templates.TemplateResponse(
        "admin/properties/form.html", {"request": request, "user": user, "mode": "create", "managers": managers}
    )


@router.post("/new")
async def property_create_submit(
    request: Request,
    name: str = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    manager_id: str = Form(""),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    managers = db.query(User).filter(User.role.in_([UserRole.CARETAKER, UserRole.ADMIN])).order_by(User.name).all()
    try:
        data = PropertyCreate(
            name=name, location=location, description=description or None,
            manager_id=uuid.UUID(manager_id) if manager_id else None,
        )
        image_url = None
        if image and image.filename:
            image_url = await save_upload(image, "properties")
        prop = create_property(db, data, image_url=image_url)
    except (PropertyServiceError, UploadError, ValueError) as e:
        return templates.TemplateResponse(
            "admin/properties/form.html",
            {"request": request, "user": user, "mode": "create", "managers": managers, "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="property", entity_id=str(prop.id),
                 description=f"Created property {prop.name}")
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/properties/{prop.id}", status_code=303)


@router.get("/{property_id}")
def property_detail(request: Request, property_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    result = get_property_with_unit_counts(db, property_id)
    if not result:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Property not found"}, status_code=404)
    return templates.TemplateResponse("admin/properties/detail.html", {"request": request, "user": user, **result})


@router.get("/{property_id}/edit")
def property_edit_form(request: Request, property_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    prop = db.get(Property, property_id)
    if not prop:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Property not found"}, status_code=404)
    managers = db.query(User).filter(User.role.in_([UserRole.CARETAKER, UserRole.ADMIN])).order_by(User.name).all()
    return templates.TemplateResponse(
        "admin/properties/form.html",
        {"request": request, "user": user, "mode": "edit", "target": prop, "managers": managers, "statuses": list(PropertyStatus)},
    )


@router.post("/{property_id}/edit")
async def property_edit_submit(
    request: Request,
    property_id: uuid.UUID,
    name: str = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    manager_id: str = Form(""),
    status_value: str = Form(..., alias="status"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    managers = db.query(User).filter(User.role.in_([UserRole.CARETAKER, UserRole.ADMIN])).order_by(User.name).all()
    try:
        data = PropertyUpdate(
            name=name, location=location, description=description or None,
            manager_id=uuid.UUID(manager_id) if manager_id else None,
            status=PropertyStatus(status_value),
        )
        image_url = None
        if image and image.filename:
            image_url = await save_upload(image, "properties")
        prop = update_property(db, property_id, data, image_url=image_url)
    except (PropertyServiceError, UploadError, ValueError) as e:
        target = db.get(Property, property_id)
        return templates.TemplateResponse(
            "admin/properties/form.html",
            {"request": request, "user": user, "mode": "edit", "target": target, "managers": managers,
             "statuses": list(PropertyStatus), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="property", entity_id=str(prop.id),
                 description=f"Updated property {prop.name}")
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/admin/properties/{prop.id}", status_code=303)


@router.post("/{property_id}/archive")
def property_archive(request: Request, property_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    import json
    prop = archive_property(db, property_id)
    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="property", entity_id=str(property_id),
                 description=f"Archived property {prop.name}")
    db.commit()
    from fastapi.responses import JSONResponse
    return JSONResponse({"status": "archived"}, headers={"HX-Trigger": json.dumps({"toast": {"type": "success", "message": f"{prop.name} archived"}})})
