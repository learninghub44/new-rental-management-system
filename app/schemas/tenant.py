from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import TenantStatus
from app.core.phone import normalize_phone


class TenantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str
    email: Optional[EmailStr] = None
    national_id: str = Field(min_length=3, max_length=30)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    create_login: bool = True

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        return normalize_phone(v) if v else v


class TenantUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    national_id: Optional[str] = Field(default=None, min_length=3, max_length=30)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    status: Optional[TenantStatus] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return normalize_phone(v) if v else v
