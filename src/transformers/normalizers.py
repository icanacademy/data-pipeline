"""Data normalization functions."""

import re
from datetime import datetime
from typing import Optional


def normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize a person's name for matching.

    Handles:
    - "John Doe" -> "john doe"
    - "Doe, John" -> "john doe"
    - "T. John" -> "john" (teacher prefix)
    - Extra whitespace
    """
    if not name:
        return None

    # Lowercase
    name = name.lower().strip()

    # Remove common prefixes
    prefixes = ["t.", "teacher", "mr.", "ms.", "mrs.", "dr."]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) :].strip()

    # Handle "Last, First" format
    if "," in name:
        parts = name.split(",")
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"

    # Remove extra whitespace
    name = " ".join(name.split())

    return name


def normalize_date(value) -> Optional[datetime]:
    """
    Normalize various date formats to datetime.

    Handles:
    - datetime objects
    - ISO format strings
    - Common date formats
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

    return None


def normalize_email(email: Optional[str]) -> Optional[str]:
    """Normalize email address."""
    if not email:
        return None
    return email.lower().strip()


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone number (keep only digits)."""
    if not phone:
        return None
    return re.sub(r"[^\d+]", "", phone)


def normalize_score(score) -> Optional[float]:
    """Normalize score values."""
    if score is None:
        return None

    if isinstance(score, (int, float)):
        return float(score)

    if isinstance(score, str):
        # Try to extract number
        match = re.search(r"[\d.]+", score)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

    return None


def normalize_boolean(value) -> bool:
    """Normalize various boolean representations."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on", "active")
    return bool(value)
