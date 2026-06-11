"""Sanitization for attacker-controlled honeypot data.

All fields extracted from OpenCanary logs are attacker-controlled.
This module strips control characters, caps field length, and validates
inputs before they reach alerting channels or AI-agent-visible surfaces.
"""

import re
from typing import Optional

# Strip ALL C0 controls incl. TAB/CR/LF — CR/LF in an attacker field that reaches
# an HTTP header (ntfy Title/Click) lets an outsider abort the send (requests
# raises InvalidHeader) and silently suppress the alert about themselves.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_MAX_FIELD_LEN = 256
_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


def sanitize(value: str) -> str:
    """Strip control characters and cap length of attacker-supplied data."""
    value = _CONTROL_CHARS.sub("", str(value))
    if len(value) > _MAX_FIELD_LEN:
        value = value[:_MAX_FIELD_LEN] + "...[truncated]"
    return value


def html_escape(value: str) -> str:
    """HTML-escape attacker data for HTML sinks. sanitize() only strips control
    chars; it does NOT neutralize < > " ' so it is insufficient for innerHTML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def header_safe(value: str) -> str:
    """Make an attacker field safe for an HTTP header (ntfy Title/Click/Tags):
    sanitize() removes CR/LF/controls; also map the middle dot and drop remaining
    non-ASCII so the latin-1 header round-trips intact instead of garbling/aborting."""
    return sanitize(value).replace("\u00b7", "-").encode("ascii", "ignore").decode()


def safe_error(exc: BaseException, label: str) -> str:
    """Client-safe error message (osint #27 - error-echo leaks).

    Raw exception strings leak operational detail: psycopg2 errors carry
    host/user/dbname, requests errors carry full URLs. Return only the label
    and the exception class; the caller logs the full detail server-side."""
    return f"{label} request failed ({type(exc).__name__}) - see server logs"


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
