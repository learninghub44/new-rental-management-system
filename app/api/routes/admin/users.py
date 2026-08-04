import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.templating import templates
from app.models.user import User, LoginHistory
from app.models.enums import UserRole, UserStatus, ActivityAction
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import (
    list_users, create_user, update_user, set_status, admin_reset_password, UserServiceError,
)
from app.services.activity_log import log_activity
from app.services.email_service import send_welcome_email

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _toast_headers(message: str, kind: str = "success") -> dict:
    import json
    return {"HX-Trigger": json.dumps({"toast": {"type": kind, "message": message}})}


@router.get("")
def users_list(
    request: Request,
    search: str = "",
    role: str = "",
    status_filter: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    role_enum = UserRole(role) if role else None
    status_enum = UserStatus(status_filter) if status_filter else None
    users, total = list_users(db, search=search or None, role=role_enum, status_filter=status_enum, page=page)
    return templates.TemplateResponse(
        "admin/users/list.html",
        {
            "request": request, "user": admin, "users": users, "total": total, "page": page,
            "search": search, "role": role, "status_filter": status_filter,
            "roles": list(UserRole), "statuses": list(UserStatus),
        },
    )


@router.get("/new")
def user_new_form(request: Request, admin: User = Depends(require_admin)):
    return templates.TemplateResponse(
        "admin/users/form.html", {"request": request, "user": admin, "roles": list(UserRole), "mode": "create"}
    )


@router.post("/new")
def user_create_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        data = UserCreate(name=name, email=email, phone=phone, role=UserRole(role))
        new_user, default_password = create_user(db, data)
    except (UserServiceError, ValueError) as e:
        return templates.TemplateResponse(
            "admin/users/form.html",
            {"request": request, "user": admin, "roles": list(UserRole), "mode": "create", "error": str(e),
             "form_data": {"name": name, "email": email, "phone": phone, "role": role}},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=admin.id, entity_type="user", entity_id=str(new_user.id),
                 description=f"Created user {new_user.email} ({new_user.role.value})")
    if new_user.email:
        send_welcome_email(db, new_user.email, new_user.name)
    db.commit()

    return templates.TemplateResponse(
        "admin/users/created.html",
        {"request": request, "user": admin, "new_user": new_user, "default_password": default_password},
    )


@router.get("/{user_id}/edit")
def user_edit_form(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = db.get(User, user_id)
    if not target:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "User not found"}, status_code=404)
    return templates.TemplateResponse(
        "admin/users/form.html",
        {"request": request, "user": admin, "roles": list(UserRole), "statuses": list(UserStatus), "mode": "edit", "target": target},
    )


@router.post("/{user_id}/edit")
def user_edit_submit(
    request: Request,
    user_id: uuid.UUID,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    role: str = Form(...),
    status_value: str = Form(..., alias="status"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        data = UserUpdate(name=name, email=email, phone=phone, role=UserRole(role), status=UserStatus(status_value))
        target = update_user(db, user_id, data)
    except (UserServiceError, ValueError) as e:
        target = db.get(User, user_id)
        return templates.TemplateResponse(
            "admin/users/form.html",
            {"request": request, "user": admin, "roles": list(UserRole), "statuses": list(UserStatus),
             "mode": "edit", "target": target, "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.UPDATE, user_id=admin.id, entity_type="user", entity_id=str(target.id),
                 description=f"Updated user {target.email}")
    db.commit()
    return templates.TemplateResponse(
        "admin/users/form.html",
        {"request": request, "user": admin, "roles": list(UserRole), "statuses": list(UserStatus),
         "mode": "edit", "target": target, "message": "User updated."},
    )


@router.post("/{user_id}/disable")
def user_disable(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = set_status(db, user_id, UserStatus.INACTIVE)
    log_activity(db, ActivityAction.UPDATE, user_id=admin.id, entity_type="user", entity_id=str(user_id),
                 description=f"Disabled user {target.email}")
    db.commit()
    return JSONResponse({"status": "disabled"}, headers=_toast_headers(f"{target.name} disabled"))


@router.post("/{user_id}/activate")
def user_activate(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = set_status(db, user_id, UserStatus.ACTIVE)
    log_activity(db, ActivityAction.UPDATE, user_id=admin.id, entity_type="user", entity_id=str(user_id),
                 description=f"Activated user {target.email}")
    db.commit()
    return JSONResponse({"status": "active"}, headers=_toast_headers(f"{target.name} activated"))


@router.post("/{user_id}/reset-password")
def user_reset_password(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        target, new_password = admin_reset_password(db, user_id)
    except UserServiceError as e:
        return JSONResponse({"error": str(e)}, status_code=400, headers=_toast_headers(str(e), "error"))

    log_activity(db, ActivityAction.UPDATE, user_id=admin.id, entity_type="user", entity_id=str(user_id),
                 description=f"Reset password for {target.email}")
    db.commit()
    return templates.TemplateResponse(
        "admin/users/password_reset_result.html",
        {"request": request, "target": target, "new_password": new_password},
    )


@router.get("/{user_id}/login-history")
def user_login_history(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target = db.get(User, user_id)
    history = (
        db.query(LoginHistory)
        .filter(LoginHistory.user_id == user_id)
        .order_by(LoginHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "admin/users/login_history.html",
        {"request": request, "user": admin, "target": target, "history": history},
    )
