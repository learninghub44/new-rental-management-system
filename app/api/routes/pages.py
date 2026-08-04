from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_tenant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment
from app.models.enums import PaymentStatus

router = APIRouter(tags=["pages"])


@router.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@router.get("/tenant/home")
def tenant_home(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    from app.services.ledger_service import get_tenant_balance

    tenant = db.query(Tenant).filter(Tenant.user_id == user.id).first()
    balance = get_tenant_balance(db, tenant.id) if tenant else 0
    recent_payment = None
    if tenant:
        recent_payment = (
            db.query(Payment)
            .filter(Payment.tenant_id == tenant.id, Payment.status == PaymentStatus.SUCCESSFUL)
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
            .first()
        )
    return templates.TemplateResponse(
        "tenant/home.html", {"request": request, "user": user, "balance": balance, "recent_payment": recent_payment},
    )


@router.get("/admin/dashboard")
def admin_dashboard(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "user": user})


@router.get("/admin/more")
def admin_more(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/more.html", {"request": request, "user": user})
