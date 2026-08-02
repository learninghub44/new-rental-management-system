"""
Enumerations shared across models. Stored as native Postgres ENUM types
via SQLAlchemy's Enum, so invalid values are rejected at the DB level too.
"""
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    CARETAKER = "caretaker"
    TENANT = "tenant"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PropertyStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class UnitStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"


class UnitType(str, enum.Enum):
    BEDSITTER = "bedsitter"
    ONE_BEDROOM = "one_bedroom"
    TWO_BEDROOM = "two_bedroom"
    THREE_BEDROOM = "three_bedroom"
    STUDIO = "studio"
    SHOP = "shop"
    OFFICE = "office"
    OTHER = "other"


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MOVED_OUT = "moved_out"
    BLACKLISTED = "blacklisted"


class LeaseStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RENEWED = "renewed"
    TERMINATED = "terminated"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class LedgerTransactionType(str, enum.Enum):
    INVOICE = "invoice"
    PAYMENT = "payment"
    PENALTY = "penalty"
    DISCOUNT = "discount"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"


class PaymentMethod(str, enum.Enum):
    PAYHERO = "payhero"
    BANK = "bank"
    CASH = "cash"
    MANUAL_ADJUSTMENT = "manual_adjustment"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REVERSED = "reversed"


class MaintenancePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class MaintenanceStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"


class ExpenseCategory(str, enum.Enum):
    REPAIR = "repair"
    WATER = "water"
    ELECTRICITY = "electricity"
    SECURITY = "security"
    CLEANING = "cleaning"
    OTHER = "other"


class ActivityAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PAYMENT = "payment"
    SETTINGS_CHANGE = "settings_change"


class ErrorLogStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class EmailStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
