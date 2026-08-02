"""
Import every model here so that Base.metadata is fully populated
before Alembic's autogenerate (or Base.metadata.create_all) runs.
"""
from app.models.user import User, LoginHistory, PasswordResetToken  # noqa: F401
from app.models.property import Property, Unit  # noqa: F401
from app.models.tenant import Tenant, Lease  # noqa: F401
from app.models.billing import Invoice, LedgerEntry  # noqa: F401
from app.models.payment import Payment, PayHeroTransaction, Receipt  # noqa: F401
from app.models.maintenance import MaintenanceRequest  # noqa: F401
from app.models.expense import Expense  # noqa: F401
from app.models.system import ErrorLog, ActivityLog, EmailLog  # noqa: F401

__all__ = [
    "User", "LoginHistory", "PasswordResetToken",
    "Property", "Unit",
    "Tenant", "Lease",
    "Invoice", "LedgerEntry",
    "Payment", "PayHeroTransaction", "Receipt",
    "MaintenanceRequest",
    "Expense",
    "ErrorLog", "ActivityLog", "EmailLog",
]
