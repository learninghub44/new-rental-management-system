import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.property import Property, Unit
from app.models.enums import UnitType, UnitStatus, ActivityAction
from app.schemas.unit import UnitCreate, UnitUpdate
from app.services.unit_service import create_unit, update_unit, mark_vacant, UnitServiceError
from app.services.activity_log import log_activity

router = APIRouter(prefix="/admin/properties/{property_id}/units", tags=["admin-units"])


@router.get("/new")
def unit_new_form(request: Request, property_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    prop = db.get(Property, property_id)
    if not prop:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Property not found"}, status_code=404)
    return templates.TemplateResponse(
        "admin/properties/unit_form.html",
        {"request": request, "user": user, "property": prop, "mode": "create", "unit_types": list(UnitType)},
    )


@router.post("/new")
def unit_create_submit(
    request: Request, property_id: uuid.UUID,
    unit_number: str = Form(...), floor: str = Form(""), unit_type: str = Form(...),
    bedrooms: int = Form(0), monthly_rent: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    prop = db.get(Property, property_id)
    try:
        data = UnitCreate(
            property_id=property_id, unit_number=unit_number, floor=floor or None,
            unit_type=UnitType(unit_type), bedrooms=bedrooms, monthly_rent=monthly_rent,
        )
        unit = create_unit(db, data)
    except (UnitServiceError, ValueError) as e:
        return templates.TemplateResponse(
            "admin/properties/unit_form.html",
            {"request": request, "user": user, "property": prop, "mode": "create", "unit_types": list(UnitType), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="unit", entity_id=str(unit.id),
                 description=f"Created unit {unit.unit_number} in {prop.name}")
    db.commit()
    return RedirectResponse(url=f"/admin/properties/{property_id}", status_code=303)


@router.get("/{unit_id}/edit")
def unit_edit_form(request: Request, property_id: uuid.UUID, unit_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    prop = db.get(Property, property_id)
    unit = db.get(Unit, unit_id)
    if not prop or not unit:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Not found"}, status_code=404)
    return templates.TemplateResponse(
        "admin/properties/unit_form.html",
        {"request": request, "user": user, "property": prop, "mode": "edit", "target": unit,
         "unit_types": list(UnitType), "statuses": list(UnitStatus)},
    )


@router.post("/{unit_id}/edit")
def unit_edit_submit(
    request: Request, property_id: uuid.UUID, unit_id: uuid.UUID,
    unit_number: str = Form(...), floor: str = Form(""), unit_type: str = Form(...),
    bedrooms: int = Form(0), monthly_rent: str = Form(...), status_value: str = Form(..., alias="status"),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    prop = db.get(Property, property_id)
    try:
        data = UnitUpdate(
            unit_number=unit_number, floor=floor or None, unit_type=UnitType(unit_type),
            bedrooms=bedrooms, monthly_rent=monthly_rent, status=UnitStatus(status_value),
        )
        unit = update_unit(db, unit_id, data)
    except (UnitServiceError, ValueError) as e:
        target = db.get(Unit, unit_id)
        return templates.TemplateResponse(
            "admin/properties/unit_form.html",
            {"request": request, "user": user, "property": prop, "mode": "edit", "target": target,
             "unit_types": list(UnitType), "statuses": list(UnitStatus), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="unit", entity_id=str(unit.id),
                 description=f"Updated unit {unit.unit_number}")
    db.commit()
    return RedirectResponse(url=f"/admin/properties/{property_id}", status_code=303)


@router.post("/{unit_id}/mark-vacant")
def unit_mark_vacant(request: Request, property_id: uuid.UUID, unit_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    import json
    unit = mark_vacant(db, unit_id)
    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="unit", entity_id=str(unit.id),
                 description=f"Marked unit {unit.unit_number} vacant")
    db.commit()
    return JSONResponse({"status": "vacant"}, headers={"HX-Trigger": json.dumps({"toast": {"type": "success", "message": f"Unit {unit.unit_number} marked vacant"}})})
