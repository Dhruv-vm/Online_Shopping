"""Indian PIN code helpers."""

from __future__ import annotations

import re

_PIN_RE = re.compile(r"^[1-9][0-9]{5}$")


def validate_pincode(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if not _PIN_RE.match(v):
        raise ValueError("pincode must be a valid 6-digit Indian PIN code")
    return v


def retailer_serves(service_pincodes: list | None, pincode: str | None) -> bool:
    """An empty service list means the retailer has not restricted its area."""
    if not pincode or not service_pincodes:
        return True
    return pincode in service_pincodes
