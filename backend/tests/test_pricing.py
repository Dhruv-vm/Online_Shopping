import pytest

from app.core.exceptions import AppException
from app.modules.pricing.discount_service import DiscountService
from app.modules.pricing.models import Discount, DiscountType
from app.modules.pricing.pricing_service import (
    DeliveryPolicy,
    calculate_retailer_delivery_fee,
    calculate_tax_breakdown,
    normalize_state_code,
    validate_state_code,
    validate_tax_classification,
)


def test_state_code_normalization():
    assert normalize_state_code("Karnataka") == "KA"
    assert normalize_state_code("KARNATAKA") == "KA"
    assert normalize_state_code("ka") == "KA"
    assert normalize_state_code("Maharashtra") == "MH"
    assert normalize_state_code("DELHI") == "DL"
    assert normalize_state_code("Tamil Nadu") == "TN"
    assert normalize_state_code(None) is None
    assert normalize_state_code("") is None
    assert normalize_state_code("UNKNOWN_STATE_XYZ") is None


def test_state_code_validation():
    assert validate_state_code("Karnataka") == "KA"
    assert validate_state_code("MH") == "MH"

    with pytest.raises(AppException) as exc_missing:
        validate_state_code(None, context="Retailer state")
    assert exc_missing.value.status_code == 422
    assert exc_missing.value.code == "MISSING_STATE"

    with pytest.raises(AppException) as exc_invalid:
        validate_state_code("Atlantis", context="Delivery state")
    assert exc_invalid.value.status_code == 422
    assert exc_invalid.value.code == "INVALID_STATE"


def test_tax_classification_validation():
    # Valid statutory classifications
    hsn, rate = validate_tax_classification("8518", 1800)
    assert hsn == "8518"
    assert rate == 1800

    # 0% statutory rate for books
    hsn_b, rate_b = validate_tax_classification("4901", 0)
    assert hsn_b == "4901"
    assert rate_b == 0

    # Missing HSN code must fail with 422
    with pytest.raises(AppException) as exc_hsn:
        validate_tax_classification(None, 1800, item_identifier="TEST-SKU")
    assert exc_hsn.value.status_code == 422
    assert exc_hsn.value.code == "INVALID_TAX_CLASSIFICATION"

    # Missing GST rate must fail with 422
    with pytest.raises(AppException) as exc_rate:
        validate_tax_classification("8518", None, item_identifier="TEST-SKU")
    assert exc_rate.value.status_code == 422
    assert exc_rate.value.code == "INVALID_TAX_CLASSIFICATION"

    # Fabricated / arbitrary rate (e.g. 13% = 1300 bps) must fail with 422
    with pytest.raises(AppException) as exc_fab:
        validate_tax_classification("8518", 1300, item_identifier="TEST-SKU")
    assert exc_fab.value.status_code == 422
    assert exc_fab.value.code == "INVALID_TAX_CLASSIFICATION"


def test_gst_calculation_intra_state_18_percent():
    # Selling price ₹1,180.00 (118,000 paise) at 18.00% (1800 basis points)
    # Retailer in KA, Delivery in KA -> Intra-state
    # Base: 118000 * 10000 / 11800 = 100000 paise (₹1,000.00)
    # Total Tax: 18000 paise (₹180.00)
    # CGST (9%): 9000 paise (₹90.00)
    # SGST (9%): 9000 paise (₹90.00)
    # IGST: 0
    res = calculate_tax_breakdown(
        selling_price_paise=118000,
        gst_rate_basis_points=1800,
        retailer_state="KA",
        delivery_state="KA",
    )
    assert res["is_intra_state"] is True
    assert res["taxable_base_paise"] == 100000
    assert res["total_tax_paise"] == 18000
    assert res["cgst_paise"] == 9000
    assert res["sgst_paise"] == 9000
    assert res["igst_paise"] == 0
    assert res["cgst_paise"] + res["sgst_paise"] == res["total_tax_paise"]
    assert res["taxable_base_paise"] + res["total_tax_paise"] == 118000


def test_gst_calculation_inter_state_18_percent():
    # Selling price ₹1,180.00 (118,000 paise) at 18.00%
    # Retailer in MH, Delivery in KA -> Inter-state
    # Base: 100000 paise
    # Total Tax: 18000 paise
    # CGST: 0, SGST: 0, IGST: 18000 paise
    res = calculate_tax_breakdown(
        selling_price_paise=118000,
        gst_rate_basis_points=1800,
        retailer_state="MH",
        delivery_state="Karnataka",
    )
    assert res["is_intra_state"] is False
    assert res["taxable_base_paise"] == 100000
    assert res["total_tax_paise"] == 18000
    assert res["cgst_paise"] == 0
    assert res["sgst_paise"] == 0
    assert res["igst_paise"] == 18000


@pytest.mark.parametrize(
    "selling_price,gst_bp,expected_tax_range",
    [
        (50000, 0, 0),  # 0% tax bracket (Books HSN 4901: ₹500.00 -> ₹0 tax)
        (10500, 500, (400, 600)),  # 5% tax bracket (₹105.00 -> ~₹5 tax)
        (11200, 1200, (1100, 1300)),  # 12% tax bracket (₹112.00 -> ~₹12 tax)
        (11800, 1800, (1700, 1900)),  # 18% tax bracket (₹118.00 -> ~₹18 tax)
        (12800, 2800, (2700, 2900)),  # 28% tax bracket (₹128.00 -> ~₹28 tax)
    ],
)
def test_gst_hsn_brackets_reconciliation(selling_price, gst_bp, expected_tax_range):
    res = calculate_tax_breakdown(
        selling_price_paise=selling_price,
        gst_rate_basis_points=gst_bp,
        retailer_state="DL",
        delivery_state="DL",
    )
    # Reconciliation invariants
    assert res["taxable_base_paise"] + res["total_tax_paise"] == selling_price
    assert (
        res["cgst_paise"] + res["sgst_paise"] + res["igst_paise"]
        == res["total_tax_paise"]
    )
    if isinstance(expected_tax_range, tuple):
        assert expected_tax_range[0] <= res["total_tax_paise"] <= expected_tax_range[1]
    else:
        assert res["total_tax_paise"] == expected_tax_range


def test_gst_odd_paise_rounding_reconciliation():
    # Odd number tax test to verify integer paise rounding does not lose 1 paise
    res = calculate_tax_breakdown(
        selling_price_paise=9999,
        gst_rate_basis_points=1800,
        retailer_state="KA",
        delivery_state="KA",
    )
    # CGST + SGST must exactly equal total_tax_paise
    assert res["cgst_paise"] + res["sgst_paise"] == res["total_tax_paise"]
    # Base + total tax must exactly equal selling price
    assert res["taxable_base_paise"] + res["total_tax_paise"] == 9999


def test_retailer_delivery_fee_configurable_policy():
    # Custom policy with ₹30 delivery fee and ₹300 free threshold
    custom_policy = DeliveryPolicy(
        default_fee_paise=3000,
        default_free_threshold_paise=30000,
    )

    # Below threshold (₹250 = 25,000 paise)
    fee, free, needed = custom_policy.calculate_fee(25000)
    assert fee == 3000
    assert free is False
    assert needed == 5000

    # Above threshold (₹350 = 35,000 paise)
    fee, free, needed = custom_policy.calculate_fee(35000)
    assert fee == 0
    assert free is True
    assert needed == 0


def test_retailer_delivery_fee_default_rules():
    # 1. Order below ₹499.00 (e.g. ₹400.00 = 40,000 paise)
    fee, free, needed = calculate_retailer_delivery_fee(40000)
    assert fee == 4900  # 4900 paise (₹49)
    assert free is False
    assert needed == 9900  # 49900 - 40000

    # 2. Exactly threshold ₹499.00 (49,900 paise)
    fee, free, needed = calculate_retailer_delivery_fee(49900)
    assert fee == 0
    assert free is True
    assert needed == 0

    # 3. Order above threshold ₹1,000.00 (100,000 paise)
    fee, free, needed = calculate_retailer_delivery_fee(100000)
    assert fee == 0
    assert free is True
    assert needed == 0


def test_discount_percentage_calculation():
    # 10% discount on ₹1,000 (100,000 paise) -> ₹100 discount (10,000 paise)
    d = Discount(
        name="10% Off",
        discount_type=DiscountType.PERCENTAGE.value,
        discount_value=1000,  # 10.00%
        is_active=True,
    )
    disc_amount, final_price = DiscountService.calculate_unit_discount(100000, [d])
    assert disc_amount == 10000
    assert final_price == 90000


def test_discount_fixed_amount_calculation():
    # ₹200 (20,000 paise) flat discount on ₹1,000 (100,000 paise)
    d = Discount(
        name="Flat ₹200 Off",
        discount_type=DiscountType.FIXED_AMOUNT.value,
        discount_value=20000,
        is_active=True,
    )
    disc_amount, final_price = DiscountService.calculate_unit_discount(100000, [d])
    assert disc_amount == 20000
    assert final_price == 80000


def test_discount_cannot_produce_negative_price():
    # ₹1,500 discount on ₹1,000 item -> capped at ₹1,000, price becomes 0
    d = Discount(
        name="Excessive Discount",
        discount_type=DiscountType.FIXED_AMOUNT.value,
        discount_value=150000,
        is_active=True,
    )
    disc_amount, final_price = DiscountService.calculate_unit_discount(100000, [d])
    assert disc_amount == 100000
    assert final_price == 0


def test_discount_percentage_cap_with_max_discount():
    # 50% discount capped at ₹250 (25,000 paise) on ₹1,000 (100,000 paise)
    d = Discount(
        name="50% Off Capped",
        discount_type=DiscountType.PERCENTAGE.value,
        discount_value=5000,  # 50%
        max_discount_paise=25000,  # Max ₹250
        is_active=True,
    )
    disc_amount, final_price = DiscountService.calculate_unit_discount(100000, [d])
    assert disc_amount == 25000  # Capped at 25000 instead of 50000
    assert final_price == 75000


def test_discounted_selling_price_gst_reconciliation():
    # MRP ₹1,180.00 (118,000 paise) with 18% GST and a ₹100.00 (10,000 paise) discount
    # Selling price after discount = 108,000 paise (₹1,080.00)
    d = Discount(
        name="₹100 Off",
        discount_type=DiscountType.FIXED_AMOUNT.value,
        discount_value=10000,
        is_active=True,
    )
    disc_amount, discounted_unit_price = DiscountService.calculate_unit_discount(
        118000, [d]
    )
    assert disc_amount == 10000
    assert discounted_unit_price == 108000

    # 3 units quantity
    quantity = 3
    line_total = discounted_unit_price * quantity  # 324,000 paise (₹3,240.00)
    assert line_total == 324000

    # GST extraction on line total
    tax_res = calculate_tax_breakdown(
        selling_price_paise=line_total,
        gst_rate_basis_points=1800,
        retailer_state="KA",
        delivery_state="KA",
    )

    # Invariants
    assert tax_res["taxable_base_paise"] + tax_res["total_tax_paise"] == line_total
    assert (
        tax_res["cgst_paise"] + tax_res["sgst_paise"] + tax_res["igst_paise"]
        == tax_res["total_tax_paise"]
    )
    assert tax_res["is_intra_state"] is True
    assert tax_res["cgst_paise"] == tax_res["sgst_paise"]
