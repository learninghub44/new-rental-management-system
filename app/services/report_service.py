"""
PDF (reportlab) and Excel (openpyxl) report generation. Each function
returns raw bytes ready to stream back as a file download.
"""
import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tenant import Tenant, Lease
from app.models.property import Property, Unit
from app.models.expense import Expense
from app.models.payment import Payment
from app.models.enums import LeaseStatus, PaymentStatus
from app.services.ledger_service import get_tenant_balance

HEADER_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])


def _pdf_header(title: str) -> list:
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(settings.COMPANY_NAME, styles["Heading2"]),
        Paragraph(title, styles["Heading3"]),
        Paragraph(f"Generated {date.today():%d %b %Y}", styles["Normal"]),
        Spacer(1, 8 * mm),
    ]
    return elements


def rent_roll_pdf(db: Session) -> bytes:
    leases = (
        db.query(Lease)
        .join(Tenant, Lease.tenant_id == Tenant.id)
        .join(Unit, Lease.unit_id == Unit.id)
        .join(Property, Unit.property_id == Property.id)
        .filter(Lease.status == LeaseStatus.ACTIVE)
        .order_by(Property.name, Unit.unit_number)
        .all()
    )

    data = [["Property", "Unit", "Tenant", "Phone", "Monthly Rent", "Balance"]]
    total_rent = Decimal("0")
    total_balance = Decimal("0")
    for lease in leases:
        balance = get_tenant_balance(db, lease.tenant_id)
        total_rent += lease.rent_amount
        total_balance += balance
        data.append([
            lease.unit.property.name, lease.unit.unit_number, lease.tenant.full_name, lease.tenant.phone,
            f"{lease.rent_amount:,.2f}", f"{balance:,.2f}",
        ])
    data.append(["", "", "", "TOTAL", f"{total_rent:,.2f}", f"{total_balance:,.2f}"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=15 * mm, bottomMargin=15 * mm)
    table = Table(data, repeatRows=1)
    table.setStyle(HEADER_STYLE)
    doc.build(_pdf_header("Rent Roll — Active Leases") + [table])
    return buffer.getvalue()


def arrears_excel(db: Session) -> bytes:
    tenants = db.query(Tenant).order_by(Tenant.full_name).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Arrears"
    headers = ["Tenant", "Phone", "Property", "Unit", "Balance (KES)"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for tenant in tenants:
        balance = get_tenant_balance(db, tenant.id)
        if balance <= 0:
            continue
        property_name = ""
        unit_number = ""
        if tenant.unit_id:
            unit = db.get(Unit, tenant.unit_id)
            if unit:
                unit_number = unit.unit_number
                prop = db.get(Property, unit.property_id)
                property_name = prop.name if prop else ""
        ws.append([tenant.full_name, tenant.phone, property_name, unit_number, float(balance)])

    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = width + 4

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def income_expense_pdf(db: Session, start: date, end: date) -> bytes:
    income = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == PaymentStatus.SUCCESSFUL, Payment.payment_date >= start, Payment.payment_date <= end)
        .scalar()
    )
    expenses_by_category = (
        db.query(Expense.category, func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.expense_date >= start, Expense.expense_date <= end)
        .group_by(Expense.category)
        .all()
    )
    total_expenses = sum((amt for _, amt in expenses_by_category), Decimal("0"))
    income = Decimal(income)

    data = [["Category", "Amount (KES)"]]
    data.append(["Income (payments received)", f"{income:,.2f}"])
    for category, amount in expenses_by_category:
        data.append([f"Expense — {category.value.title()}", f"{Decimal(amount):,.2f}"])
    data.append(["Total Expenses", f"{total_expenses:,.2f}"])
    data.append(["Net Income", f"{(income - total_expenses):,.2f}"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    table = Table(data, colWidths=[100 * mm, 60 * mm])
    table.setStyle(HEADER_STYLE)
    title = f"Income vs Expenses — {start:%d %b %Y} to {end:%d %b %Y}"
    doc.build(_pdf_header(title) + [table])
    return buffer.getvalue()
