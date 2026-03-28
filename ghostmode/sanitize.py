"""Sanitization for attacker-controlled honeypot data.

All fields extracted from OpenCanary logs are attacker-controlled.
This module strips control characters, caps field length, and validates
inputs before they reach alerting channels or AI-agent-visible surfaces.
"""

import re
from typing import Optional

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_MAX_FIELD_LEN = 256
_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


def sanitize(value: str) -> str:
    """Strip control characters and cap length of attacker-supplied data."""
    value = _CONTROL_CHARS.sub("", str(value))
    if len(value) > _MAX_FIELD_LEN:
        value = value[:_MAX_FIELD_LEN] + "...[truncated]"
    return value


def validate_phone(phone: Optional[str]) -> bool:
    """Validate E.164 phone number format."""
    if not phone:
        return False
    return bool(_PHONE_RE.match(phone))


def validate_url(url: Optional[str]) -> bool:
    """Validate HTTP/HTTPS URL."""
    if not url:
        return False
    return bool(_URL_RE.match(url))
