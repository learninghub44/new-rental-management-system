"""
Generates a PDF receipt for a successful payment and stores it via
app/services/storage.py (local disk in dev, S3-compatible storage in prod).
"""
import io
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment, Receipt
from app.models.tenant import Tenant
from app.services.storage import save_bytes, StorageError


def _next_receipt_number(db: Session) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m")
    count_this_month = db.query(Receipt).filter(Receipt.receipt_number.like(f"RCT-{stamp}-%")).count()
    return f"RCT-{stamp}-{count_this_month + 1:04d}"


def _render_pdf(receipt_number: str, payment: Payment, tenant: Tenant) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5

    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(15 * mm, y, settings.COMPANY_NAME)
    y -= 7 * mm
    c.setFont("Helvetica", 9)
    if settings.COMPANY_ADDRESS:
        c.drawString(15 * mm, y, settings.COMPANY_ADDRESS)
        y -= 5 * mm
    if settings.COMPANY_PHONE or settings.COMPANY_EMAIL:
        c.drawString(15 * mm, y, f"{settings.COMPANY_PHONE}  {settings.COMPANY_EMAIL}".strip())
        y -= 8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "PAYMENT RECEIPT")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    rows = [
        ("Receipt No.", receipt_number),
        ("Date", payment.payment_date.strftime("%d %b %Y")),
        ("Tenant", tenant.full_name),
        ("Phone", tenant.phone),
        ("Method", payment.method.value.replace("_", " ").title()),
        ("Reference", payment.reference or payment.transaction_id or "—"),
    ]
    for label, value in rows:
        c.drawString(15 * mm, y, f"{label}:")
        c.drawString(55 * mm, y, str(value))
        y -= 6 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Amount Paid:")
    c.drawString(55 * mm, y, f"KES {payment.amount:,.2f}")
    y -= 12 * mm

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(15 * mm, y, "This is a computer-generated receipt.")

    c.showPage()
    c.save()
    return buffer.getvalue()


def generate_receipt(db: Session, payment: Payment) -> Receipt:
    existing = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
    if existing:
        return existing

    tenant = db.get(Tenant, payment.tenant_id)
    receipt_number = _next_receipt_number(db)

    filename = f"{receipt_number}.pdf"
    pdf_url = None

    try:
        pdf_bytes = _render_pdf(receipt_number, payment, tenant)
        pdf_url = save_bytes(pdf_bytes, "receipts", filename, content_type="application/pdf")
    except (StorageError, Exception):  # noqa: BLE001 — the receipt record must still exist even if PDF generation/storage fails
        pdf_url = None

    receipt = Receipt(payment_id=payment.id, receipt_number=receipt_number, pdf_url=pdf_url)
    db.add(receipt)
    db.flush()
    return receipt
