import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.property import Property
from app.schemas.expense import ExpenseCreate, ExpenseUpdate


class ExpenseServiceError(Exception):
    pass


def create_expense(db: Session, data: ExpenseCreate, recorded_by_user_id: uuid.UUID) -> Expense:
    property_id = uuid.UUID(data.property_id)
    if not db.get(Property, property_id):
        raise ExpenseServiceError("Property not found")

    expense = Expense(
        property_id=property_id,
        category=data.category,
        description=data.description.strip(),
        amount=data.amount,
        expense_date=data.expense_date,
        attachment_url=data.attachment_url,
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(expense)
    db.flush()
    return expense


def update_expense(db: Session, expense_id: uuid.UUID, data: ExpenseUpdate) -> Expense:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise ExpenseServiceError("Expense not found")

    if data.category:
        expense.category = data.category
    if data.description:
        expense.description = data.description.strip()
    if data.amount is not None:
        expense.amount = data.amount
    if data.expense_date:
        expense.expense_date = data.expense_date
    if data.attachment_url is not None:
        expense.attachment_url = data.attachment_url

    db.add(expense)
    db.flush()
    return expense


def delete_expense(db: Session, expense_id: uuid.UUID) -> None:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise ExpenseServiceError("Expense not found")
    db.delete(expense)
    db.flush()


def list_expenses(
    db: Session, property_id: Optional[uuid.UUID] = None, page: int = 1, page_size: int = 20,
) -> tuple[list[Expense], int]:
    query = db.query(Expense)
    if property_id:
        query = query.filter(Expense.property_id == property_id)
    total = query.count()
    items = query.order_by(Expense.expense_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
