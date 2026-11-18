import uuid
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppException

# Official 2-letter state / union territory codes in India
VALID_INDIAN_STATE_CODES: set[str] = {
    "AP",  # Andhra Pradesh
    "AR",  # Arunachal Pradesh
    "AS",  # Assam
    "BR",  # Bihar
    "CG",  # Chhattisgarh
    "GA",  # Goa
    "GJ",  # Gujarat
    "HR",  # Haryana
    "HP",  # Himachal Pradesh
    "JH",  # Jharkhand
    "KA",  # Karnataka
    "KL",  # Kerala
    "MP",  # Madhya Pradesh
    "MH",  # Maharashtra
    "MN",  # Manipur
    "ML",  # Meghalaya
    "MZ",  # Mizoram
    "NL",  # Nagaland
    "OD",  # Odisha
    "PB",  # Punjab
    "RJ",  # Rajasthan
    "SK",  # Sikkim
    "TN",  # Tamil Nadu
    "TS",  # Telangana
    "TR",  # Tripura
    "UP",  # Uttar Pradesh
    "UK",  # Uttarakhand
    "WB",  # West Bengal
    "AN",  # Andaman and Nicobar Islands
    "CH",  # Chandigarh
    "DN",  # Dadra and Nagar Haveli and Daman and Diu
    "DL",  # Delhi
    "JK",  # Jammu and Kashmir
    "LA",  # Ladakh
    "LD",  # Lakshadweep
    "PY",  # Puducherry
}

INDIAN_STATE_CODE_MAP: dict[str, str] = {
    "AP": "AP",
    "ANDHRA PRADESH": "AP",
    "AR": "AR",
    "ARUNACHAL PRADESH": "AR",
    "AS": "AS",
    "ASSAM": "AS",
    "BR": "BR",
    "BIHAR": "BR",
    "CG": "CG",
    "CHHATTISGARH": "CG",
    "GA": "GA",
    "GOA": "GA",
    "GJ": "GJ",
    "GUJARAT": "GJ",
    "HR": "HR",
    "HARYANA": "HR",
    "HP": "HP",
    "HIMACHAL PRADESH": "HP",
    "JH": "JH",
    "JHARKHAND": "JH",
    "KA": "KA",
    "KARNATAKA": "KA",
    "KL": "KL",
    "KERALA": "KL",
    "MP": "MP",
    "MADHYA PRADESH": "MP",
    "MH": "MH",
    "MAHARASHTRA": "MH",
    "MN": "MN",
    "MANIPUR": "MN",
    "ML": "ML",
    "MEGHALAYA": "ML",
    "MZ": "MZ",
    "MIZORAM": "MZ",
    "NL": "NL",
    "NAGALAND": "NL",
    "OD": "OD",
    "ODISHA": "OD",
    "ORISSA": "OD",
    "PB": "PB",
    "PUNJAB": "PB",
    "RJ": "RJ",
    "RAJASTHAN": "RJ",
    "SK": "SK",
    "SIKKIM": "SK",
    "TN": "TN",
    "TAMIL NADU": "TN",
    "TS": "TS",
    "TELANGANA": "TS",
    "TR": "TR",
    "TRIPURA": "TR",
    "UP": "UP",
    "UTTAR PRADESH": "UP",
    "UK": "UK",
    "UTTARAKHAND": "UK",
    "WB": "WB",
    "WEST BENGAL": "WB",
    "AN": "AN",
    "ANDAMAN AND NICOBAR ISLANDS": "AN",
    "CH": "CH",
    "CHANDIGARH": "CH",
    "DN": "DN",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "DN",
    "DL": "DL",
    "DELHI": "DL",
    "NATIONAL CAPITAL TERRITORY OF DELHI": "DL",
    "JK": "JK",
    "JAMMU AND KASHMIR": "JK",
    "LA": "LA",
    "LADAKH": "LA",
    "LD": "LD",
    "LAKSHADWEEP": "LD",
    "PY": "PY",
    "PUDUCHERRY": "PY",
    "PONDICHERRY": "PY",
}

# Statutory Indian GST Rates in basis points (100 basis points = 1.00%)
# 0% = Books, unbranded fresh food (NIL rate)
# 5% = Packaged staples, basic apparel <= ₹1,000, edible oils
# 12% = Processed foods, fitness equipment, apparel > ₹1,000, bed linen
# 18% = Electronics, computing, personal care, general goods
# 28% = Luxury goods, automobiles
VALID_GST_RATES_BASIS_POINTS: set[int] = {0, 500, 1200, 1800, 2800}


def normalize_state_code(state_str: str | None) -> str | None:
    """Normalize state name or code to uppercase 2-letter Indian state code.

    Returns None if missing, blank, or unmapped. Never silently defaults to KA.
    """
    if not state_str:
        return None
    cleaned = state_str.strip().upper()
    return INDIAN_STATE_CODE_MAP.get(cleaned)


def validate_state_code(state_str: str | None, context: str = "State") -> str:
    """Validate and return normalized 2-letter Indian state code, or raise 422 AppException."""
    if not state_str or not state_str.strip():
        raise AppException(
            code="MISSING_STATE",
            message=f"{context} is required for statutory tax determination.",
            status_code=422,
        )
    normalized = normalize_state_code(state_str)
    if not normalized or normalized not in VALID_INDIAN_STATE_CODES:
        raise AppException(
            code="INVALID_STATE",
            message=f"{context} '{state_str}' is not a recognized Indian state or union territory.",
            status_code=422,
        )
    return normalized


def validate_tax_classification(
    hsn_code: str | None,
    gst_rate_basis_points: int | None,
    item_identifier: str = "item",
) -> tuple[str, int]:
    """Validate that product listing has an explicit, valid statutory HSN code and GST rate.

    Rejects unconfigured, missing, or fabricated GST rates with a 422 AppException.
    """
    if not hsn_code or not hsn_code.strip():
        raise AppException(
            code="INVALID_TAX_CLASSIFICATION",
            message=f"Product listing '{item_identifier}' has no statutory HSN classification configured.",
            status_code=422,
            details={"item": item_identifier, "reason": "MISSING_HSN"},
        )
    cleaned_hsn = hsn_code.strip()
    if (
        gst_rate_basis_points is None
        or gst_rate_basis_points not in VALID_GST_RATES_BASIS_POINTS
    ):
        raise AppException(
            code="INVALID_TAX_CLASSIFICATION",
            message=(
                f"Product listing '{item_identifier}' has an invalid statutory GST rate ({gst_rate_basis_points} bps). "
                f"Must be an approved Indian GST bracket: 0%, 5%, 12%, 18%, or 28%."
            ),
            status_code=422,
            details={
                "item": item_identifier,
                "hsn_code": cleaned_hsn,
                "gst_rate_basis_points": gst_rate_basis_points,
                "valid_rates_basis_points": sorted(VALID_GST_RATES_BASIS_POINTS),
            },
        )
    return cleaned_hsn, gst_rate_basis_points


class DeliveryPolicy:
    """Configurable multi-retailer delivery policy engine.

    Keeps delivery calculation completely decoupled from product catalogue pricing and GST.
    Supports platform defaults (from settings) and per-retailer threshold overrides.
    """

    def __init__(
        self,
        default_fee_paise: int | None = None,
        default_free_threshold_paise: int | None = None,
        retailer_overrides: dict[str, dict[str, int]] | None = None,
    ):
        self.default_fee_paise = (
            default_fee_paise
            if default_fee_paise is not None
            else settings.DEFAULT_DELIVERY_FEE_PAISE
        )
        self.default_free_threshold_paise = (
            default_free_threshold_paise
            if default_free_threshold_paise is not None
            else settings.DEFAULT_FREE_DELIVERY_THRESHOLD_PAISE
        )
        self.retailer_overrides = retailer_overrides or {}

    def calculate_fee(
        self,
        retailer_subtotal_paise: int,
        retailer_id: uuid.UUID | str | None = None,
    ) -> tuple[int, bool, int]:
        """Calculate delivery fee for a single retailer.

        Returns:
            (fee_paise, qualifies_for_free_delivery, amount_needed_for_free_delivery_paise)
        """
        threshold = self.default_free_threshold_paise
        standard_fee = self.default_fee_paise

        if retailer_id:
            r_key = str(retailer_id)
            if r_key in self.retailer_overrides:
                r_conf = self.retailer_overrides[r_key]
                threshold = r_conf.get("free_threshold_paise", threshold)
                standard_fee = r_conf.get("standard_fee_paise", standard_fee)

        if retailer_subtotal_paise >= threshold:
            return 0, True, 0

        amount_needed = max(0, threshold - retailer_subtotal_paise)
        return standard_fee, False, amount_needed


# Default singleton instance using application configuration
default_delivery_policy = DeliveryPolicy()


def calculate_retailer_delivery_fee(
    retailer_subtotal_paise: int,
    retailer_id: uuid.UUID | str | None = None,
    policy: DeliveryPolicy | None = None,
) -> tuple[int, bool, int]:
    """Calculate delivery fee for a single retailer using configured policy."""
    active_policy = policy or default_delivery_policy
    return active_policy.calculate_fee(
        retailer_subtotal_paise=retailer_subtotal_paise,
        retailer_id=retailer_id,
    )


def calculate_tax_breakdown(
    selling_price_paise: int,
    gst_rate_basis_points: int,
    retailer_state: str,
    delivery_state: str | None,
) -> dict[str, Any]:
    """Calculate server-authoritative GST tax breakdown in integer paise.

    Indian B2C retail requires GST-inclusive display prices.
    Base Taxable Amount = round(Selling Price * 10000 / (10000 + gst_rate_basis_points))
    Total Tax = Selling Price - Base Taxable Amount

    Intra-state (retailer_state == delivery_state):
      CGST = round(Total Tax / 2)
      SGST = Total Tax - CGST
      IGST = 0
    Inter-state (retailer_state != delivery_state):
      IGST = Total Tax
      CGST = 0
      SGST = 0

    Rounding Invariants:
      Taxable Base + Total Tax == Selling Price (Exact)
      CGST + SGST + IGST == Total Tax (Exact)
    """
    if selling_price_paise <= 0 or gst_rate_basis_points <= 0:
        return {
            "taxable_base_paise": max(0, selling_price_paise),
            "cgst_paise": 0,
            "sgst_paise": 0,
            "igst_paise": 0,
            "total_tax_paise": 0,
            "is_intra_state": True,
        }

    # Extract GST-inclusive base amount mathematically
    taxable_base = round(
        (selling_price_paise * 10000) / (10000 + gst_rate_basis_points)
    )
    total_tax = selling_price_paise - taxable_base

    r_state = normalize_state_code(retailer_state) or retailer_state
    d_state = normalize_state_code(delivery_state) if delivery_state else r_state
    is_intra_state = r_state == d_state

    if is_intra_state:
        cgst = round(total_tax / 2)
        sgst = total_tax - cgst
        igst = 0
    else:
        cgst = 0
        sgst = 0
        igst = total_tax

    return {
        "taxable_base_paise": taxable_base,
        "cgst_paise": cgst,
        "sgst_paise": sgst,
        "igst_paise": igst,
        "total_tax_paise": total_tax,
        "is_intra_state": is_intra_state,
    }
