"""
Generates a PDF receipt for a successful payment and stores it under
app/static/uploads/receipts/, mirroring the pattern in upload_service.py.
"""
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment, Receipt
from app.models.tenant import Tenant


def _next_receipt_number(db: Session) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m")
    count_this_month = db.query(Receipt).filter(Receipt.receipt_number.like(f"RCT-{stamp}-%")).count()
    return f"RCT-{stamp}-{count_this_month + 1:04d}"


def _render_pdf(path: Path, receipt_number: str, payment: Payment, tenant: Tenant) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A5)
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


def generate_receipt(db: Session, payment: Payment) -> Receipt:
    existing = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
    if existing:
        return existing

    tenant = db.get(Tenant, payment.tenant_id)
    receipt_number = _next_receipt_number(db)

    filename = f"{receipt_number}.pdf"
    target_path = Path(settings.UPLOAD_DIR) / "receipts" / filename
    pdf_url = f"/static/uploads/receipts/{filename}"

    try:
        _render_pdf(target_path, receipt_number, payment, tenant)
    except Exception:  # noqa: BLE001 — the receipt record must still exist even if PDF rendering fails
        pdf_url = None

    receipt = Receipt(payment_id=payment.id, receipt_number=receipt_number, pdf_url=pdf_url)
    db.add(receipt)
    db.flush()
    return receipt
