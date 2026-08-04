from fastapi import APIRouter, Depends, Request

from app.core.deps import require_tenant, require_staff
from app.core.templating import templates
from app.models.user import User

router = APIRouter(tags=["pages"])


@router.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@router.get("/tenant/home")
def tenant_home(request: Request, user: User = Depends(require_tenant)):
    return templates.TemplateResponse("tenant/home.html", {"request": request, "user": user})


@router.get("/admin/dashboard")
def admin_dashboard(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "user": user})


@router.get("/admin/more")
def admin_more(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/more.html", {"request": request, "user": user})
