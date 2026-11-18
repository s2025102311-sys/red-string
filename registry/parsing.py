"""Small helpers that turn raw form strings into Python values."""
from datetime import date, datetime

from .exceptions import ValidationError


def parse_date(value, default=None, label="Date"):
    """YYYY-MM-DD string -> date. Blank returns `default`; bad input raises ValidationError."""
    value = (value or "").strip()
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{label} is not a valid date.") from None


def to_float(value, label="Value"):
    """String -> float, or ValidationError."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number.") from None


def today():
    return date.today()
