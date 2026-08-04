"""
Shared helpers used across user/tenant creation flows.
"""
import re


def default_password_from_phone(phone: str) -> str:
    """
    The last 6 digits of a phone number, used as the initial login password
    for accounts created by an admin (per business rule — no self sign-up).
    Raises ValueError if the phone doesn't contain at least 6 digits.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 6:
        raise ValueError("Phone number must contain at least 6 digits to derive a default password")
    return digits[-6:]


def normalize_phone(phone: str) -> str:
    """
    Normalizes Kenyan phone numbers to a consistent +254XXXXXXXXX form.
    Accepts 07XXXXXXXX, 01XXXXXXXX, 2547XXXXXXXX, +2547XXXXXXXX.
    """
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("254"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 9:
        raise ValueError("Invalid Kenyan phone number")
    return f"+254{digits}"
