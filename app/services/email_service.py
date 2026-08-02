"""
SMTP email sending with per-message logging to EmailLog.
Templates are simple f-string based for now — swap for Jinja2 email
templates in app/templates/emails/ as the email catalogue grows.
"""
import asyncio
import logging

import aiosmtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.system import EmailLog
from app.models.enums import EmailStatus

logger = logging.getLogger("rental_app.email")


def _send_sync(to_email: str, subject: str, html_body: str) -> None:
    """Runs the async SMTP send in a fresh event loop (safe to call from sync route handlers)."""
    asyncio.run(_send_async(to_email, subject, html_body))


async def _send_async(to_email: str, subject: str, html_body: str) -> None:
    if not settings.SMTP_HOST:
        logger.warning("SMTP not configured; skipping send to %s (subject=%s)", to_email, subject)
        return

    message = EmailMessage()
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        start_tls=settings.SMTP_USE_TLS,
    )


def _dispatch(db: Session, to_email: str, subject: str, html_body: str, template_name: str) -> EmailLog:
    log_entry = EmailLog(recipient=to_email, subject=subject, template_name=template_name, status=EmailStatus.QUEUED)
    db.add(log_entry)
    db.flush()

    try:
        _send_sync(to_email, subject, html_body)
        log_entry.status = EmailStatus.SENT
    except Exception as exc:  # noqa: BLE001 — we log and continue; email failure must not break the request
        logger.error("Email send failed to %s: %s", to_email, exc)
        log_entry.status = EmailStatus.FAILED
        log_entry.error_message = str(exc)

    db.add(log_entry)
    db.commit()
    return log_entry


def send_welcome_email(db: Session, to_email: str, tenant_name: str) -> EmailLog:
    subject = f"Welcome to {settings.COMPANY_NAME}"
    body = f"<p>Hi {tenant_name},</p><p>Your tenant account has been created. You can now log in to view your balance and pay rent online.</p>"
    return _dispatch(db, to_email, subject, body, "welcome")


def send_invoice_notification_email(db: Session, to_email: str, tenant_name: str, invoice_number: str, amount: str, due_date: str) -> EmailLog:
    subject = f"New Invoice {invoice_number} — {settings.COMPANY_NAME}"
    body = (
        f"<p>Hi {tenant_name},</p>"
        f"<p>A new invoice <strong>{invoice_number}</strong> for <strong>KES {amount}</strong> has been generated, "
        f"due on {due_date}.</p>"
    )
    return _dispatch(db, to_email, subject, body, "invoice_notification")


def send_payment_receipt_email(db: Session, to_email: str, tenant_name: str, amount: str, receipt_number: str) -> EmailLog:
    subject = f"Payment Received — Receipt {receipt_number}"
    body = f"<p>Hi {tenant_name},</p><p>We've received your payment of <strong>KES {amount}</strong>. Receipt: {receipt_number}.</p>"
    return _dispatch(db, to_email, subject, body, "payment_receipt")


def send_rent_reminder_email(db: Session, to_email: str, tenant_name: str, balance: str, due_date: str) -> EmailLog:
    subject = f"Rent Reminder — {settings.COMPANY_NAME}"
    body = f"<p>Hi {tenant_name},</p><p>This is a reminder that your outstanding balance of <strong>KES {balance}</strong> is due on {due_date}.</p>"
    return _dispatch(db, to_email, subject, body, "rent_reminder")


def send_lease_expiry_email(db: Session, to_email: str, tenant_name: str, end_date: str) -> EmailLog:
    subject = f"Lease Expiry Notice — {settings.COMPANY_NAME}"
    body = f"<p>Hi {tenant_name},</p><p>Your lease is set to expire on {end_date}. Please contact us to discuss renewal.</p>"
    return _dispatch(db, to_email, subject, body, "lease_expiry")


def send_maintenance_update_email(db: Session, to_email: str, tenant_name: str, title: str, status: str) -> EmailLog:
    subject = f"Maintenance Update — {title}"
    body = f"<p>Hi {tenant_name},</p><p>Your maintenance request '<strong>{title}</strong>' is now <strong>{status}</strong>.</p>"
    return _dispatch(db, to_email, subject, body, "maintenance_update")


def send_password_reset_email(db: Session, to_email: str, name: str, reset_link: str) -> EmailLog:
    subject = f"Password Reset — {settings.COMPANY_NAME}"
    body = f"<p>Hi {name},</p><p>Click the link below to reset your password. This link expires in 1 hour.</p><p><a href='{reset_link}'>{reset_link}</a></p>"
    return _dispatch(db, to_email, subject, body, "password_reset")


def send_payment_failure_admin_email(db: Session, admin_email: str, tenant_name: str, reason: str) -> EmailLog:
    subject = "Payment Failure Alert"
    body = f"<p>Payment failed for tenant <strong>{tenant_name}</strong>.</p><p>Reason: {reason}</p>"
    return _dispatch(db, admin_email, subject, body, "payment_failure_admin")


def send_system_error_admin_email(db: Session, admin_email: str, module: str, message: str) -> EmailLog:
    subject = f"System Error in {module}"
    body = f"<p>An error occurred in <strong>{module}</strong>:</p><p>{message}</p>"
    return _dispatch(db, admin_email, subject, body, "system_error_admin")
