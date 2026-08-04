from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin_or_accountant
from app.core.templating import templates
from app.models.user import User
from app.services.report_service import rent_roll_pdf, arrears_excel, income_expense_pdf

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


@router.get("")
def reports_index(request: Request, user: User = Depends(require_admin_or_accountant)):
    return templates.TemplateResponse("admin/reports/index.html", {"request": request, "user": user})


@router.get("/rent-roll.pdf")
def report_rent_roll(db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    pdf_bytes = rent_roll_pdf(db)
    return Response(pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=rent-roll.pdf"})


@router.get("/arrears.xlsx")
def report_arrears(db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    xlsx_bytes = arrears_excel(db)
    return Response(
        xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=arrears.xlsx"},
    )


@router.get("/income-expense.pdf")
def report_income_expense(start: str = "", end: str = "", db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date.replace(day=1)
    pdf_bytes = income_expense_pdf(db, start_date, end_date)
    return Response(pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=income-expense.pdf"})
