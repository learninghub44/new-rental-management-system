import uuid
import json

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin_or_accountant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.property import Property
from app.models.enums import ExpenseCategory, ActivityAction
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.expense_service import create_expense, update_expense, delete_expense, list_expenses, ExpenseServiceError
from app.services.activity_log import log_activity

router = APIRouter(prefix="/admin/expenses", tags=["admin-expenses"])


@router.get("")
def expenses_list(
    request: Request, property_id: str = "", page: int = 1,
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    prop_uuid = uuid.UUID(property_id) if property_id else None
    expenses, total = list_expenses(db, property_id=prop_uuid, page=page)
    properties = db.query(Property).order_by(Property.name).all()
    return templates.TemplateResponse(
        "admin/expenses/list.html",
        {"request": request, "user": user, "expenses": expenses, "total": total,
         "properties": properties, "selected_property_id": property_id},
    )


@router.get("/new")
def expense_new_form(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    properties = db.query(Property).order_by(Property.name).all()
    return templates.TemplateResponse(
        "admin/expenses/form.html", {"request": request, "user": user, "mode": "create", "properties": properties, "categories": list(ExpenseCategory)},
    )


@router.post("/new")
def expense_create_submit(
    request: Request,
    property_id: str = Form(...), category: str = Form(...), description: str = Form(...),
    amount: str = Form(...), expense_date: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    try:
        data = ExpenseCreate(property_id=property_id, category=category, description=description, amount=amount, expense_date=expense_date)
        expense = create_expense(db, data, recorded_by_user_id=user.id)
    except (ExpenseServiceError, ValueError) as e:
        properties = db.query(Property).order_by(Property.name).all()
        return templates.TemplateResponse(
            "admin/expenses/form.html",
            {"request": request, "user": user, "mode": "create", "properties": properties, "categories": list(ExpenseCategory), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="expense", entity_id=str(expense.id),
                 description=f"Recorded {expense.category.value} expense of {expense.amount}")
    db.commit()
    return RedirectResponse(url="/admin/expenses", status_code=303)


@router.get("/{expense_id}/edit")
def expense_edit_form(request: Request, expense_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    from app.models.expense import Expense
    expense = db.get(Expense, expense_id)
    if not expense:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Expense not found"}, status_code=404)
    properties = db.query(Property).order_by(Property.name).all()
    return templates.TemplateResponse(
        "admin/expenses/form.html",
        {"request": request, "user": user, "mode": "edit", "target": expense, "properties": properties, "categories": list(ExpenseCategory)},
    )


@router.post("/{expense_id}/edit")
def expense_edit_submit(
    request: Request, expense_id: uuid.UUID,
    category: str = Form(...), description: str = Form(...), amount: str = Form(...), expense_date: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    try:
        data = ExpenseUpdate(category=category, description=description, amount=amount, expense_date=expense_date)
        update_expense(db, expense_id, data)
    except (ExpenseServiceError, ValueError) as e:
        from app.models.expense import Expense
        target = db.get(Expense, expense_id)
        properties = db.query(Property).order_by(Property.name).all()
        return templates.TemplateResponse(
            "admin/expenses/form.html",
            {"request": request, "user": user, "mode": "edit", "target": target, "properties": properties,
             "categories": list(ExpenseCategory), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="expense", entity_id=str(expense_id), description="Updated expense")
    db.commit()
    return RedirectResponse(url="/admin/expenses", status_code=303)


@router.post("/{expense_id}/delete")
def expense_delete_submit(request: Request, expense_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    try:
        delete_expense(db, expense_id)
    except ExpenseServiceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    log_activity(db, ActivityAction.DELETE, user_id=user.id, entity_type="expense", entity_id=str(expense_id), description="Deleted expense")
    db.commit()
    return JSONResponse({"status": "deleted"}, headers={"HX-Trigger": json.dumps({"toast": {"type": "success", "message": "Expense deleted"}})})
