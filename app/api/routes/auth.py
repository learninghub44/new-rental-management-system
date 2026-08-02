from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, COOKIE_NAME
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    hash_token,
    verify_token_hash,
    hash_password,
)
from app.core.templating import templates
from app.core.config import settings
from app.models.user import User, LoginHistory, PasswordResetToken
from app.models.enums import ActivityAction
from app.services.auth_service import authenticate_user, change_password, AuthError
from app.services.activity_log import log_activity
from app.services.email_service import send_password_reset_email

router = APIRouter(tags=["auth"])

ACCESS_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _role_home_path(role: str) -> str:
    return {
        "admin": "/admin/dashboard",
        "accountant": "/admin/dashboard",
        "caretaker": "/admin/dashboard",
        "tenant": "/tenant/home",
    }.get(role, "/login")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(db, email, password)
    except AuthError as e:
        db.add(LoginHistory(
            user_id=None, attempted_email=email.lower().strip(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"), successful=False,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return templates.TemplateResponse(
            "auth/login.html", {"request": request, "error": str(e)}, status_code=status.HTTP_400_BAD_REQUEST
        )

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.role.value)

    db.add(LoginHistory(
        user_id=user.id, ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"), successful=True,
        created_at=datetime.now(timezone.utc),
    ))
    log_activity(db, ActivityAction.LOGIN, user_id=user.id,
                 ip_address=request.client.host if request.client else None)
    db.commit()

    redirect_url = _role_home_path(user.role.value)
    resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    is_prod = settings.ENVIRONMENT == "production"
    resp.set_cookie(COOKIE_NAME, access_token, httponly=True, secure=is_prod, samesite="lax",
                     max_age=ACCESS_COOKIE_MAX_AGE)
    resp.set_cookie("refresh_token", refresh_token, httponly=True, secure=is_prod, samesite="lax",
                     max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    return resp


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    log_activity(db, ActivityAction.LOGOUT, user_id=user.id,
                 ip_address=request.client.host if request.client else None)
    db.commit()
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(COOKIE_NAME)
    resp.delete_cookie("refresh_token")
    return resp


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})


@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    # Always show the same message — do not reveal whether the email exists.
    if user:
        raw_token = create_password_reset_token()
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_at=datetime.now(timezone.utc),
        )
        db.add(reset)
        db.commit()
        reset_link = f"{settings.BASE_URL}/reset-password?token={raw_token}&uid={user.id}"
        send_password_reset_email(db, user.email, user.name, reset_link)

    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "message": "If that email is registered, a reset link has been sent."},
    )


@router.get("/reset-password")
def reset_password_page(request: Request, token: str, uid: str):
    return templates.TemplateResponse("auth/reset_password.html", {"request": request, "token": token, "uid": uid})


@router.post("/reset-password")
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    uid: str = Form(...),
    new_password: str = Form(..., min_length=8),
    db: Session = Depends(get_db),
):
    import uuid as uuid_mod

    try:
        user_id = uuid_mod.UUID(uid)
    except ValueError:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "uid": uid, "error": "Invalid or expired reset link."},
            status_code=400,
        )

    reset_entry = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )

    valid = (
        reset_entry is not None
        and reset_entry.expires_at > datetime.now(timezone.utc)
        and verify_token_hash(token, reset_entry.token_hash)
    )
    if not valid:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "uid": uid, "error": "Invalid or expired reset link."},
            status_code=400,
        )

    user = db.get(User, user_id)
    user.password_hash = hash_password(new_password)
    reset_entry.used_at = datetime.now(timezone.utc)
    db.add_all([user, reset_entry])
    db.commit()

    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/settings/change-password")
def change_password_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("auth/change_password.html", {"request": request, "user": user})


@router.post("/settings/change-password")
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(..., min_length=8),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        change_password(db, user, current_password, new_password)
    except AuthError as e:
        return templates.TemplateResponse(
            "auth/change_password.html", {"request": request, "user": user, "error": str(e)}, status_code=400
        )
    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="user", entity_id=str(user.id),
                 description="Changed own password")
    db.commit()
    return templates.TemplateResponse(
        "auth/change_password.html", {"request": request, "user": user, "message": "Password updated successfully."}
    )
