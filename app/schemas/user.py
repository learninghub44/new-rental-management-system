import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import UserRole, UserStatus
from app.core.phone import normalize_phone


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str
    role: UserRole

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return normalize_phone(v) if v else v


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: Optional[str]
    role: UserRole
    status: UserStatus
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
