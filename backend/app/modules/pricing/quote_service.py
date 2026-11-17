import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppException
from app.modules.cart.models import Cart
from app.modules.cart.repository import CartRepository
from app.modules.catalogue.models import (
    ProductListing,
    ProductVariant,
)
from app.modules.identity.models import Address
from app.modules.pricing.discount_service import DiscountService
from app.modules.pricing.models import (
    CheckoutQuote,
    CheckoutQuoteItem,
    QuoteStatus,
)
from app.modules.pricing.pricing_service import (
    calculate_retailer_delivery_fee,
    calculate_tax_breakdown,
    validate_state_code,
    validate_tax_classification,
)
from app.modules.pricing.schemas import (
    QuoteResponse,
    QuoteValidationIssue,
    QuoteValidationResponse,
    RetailerPricingBreakdownSchema,
)

QUOTE_TTL_MINUTES = 15


class QuoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.discount_service = DiscountService(session)

    async def generate_quote_from_cart(
        self,
        cart: Cart,
        delivery_address_id: uuid.UUID | None = None,
        delivery_state: str | None = None,
    ) -> CheckoutQuote:
        """Generate a server-authoritative, persistent pricing quote from a cart."""
        cart_repo = CartRepository(self.session)
        cart_items = await cart_repo.get_cart_items(cart.id)
        if not cart_items:
            raise AppException(
                code="EMPTY_CART",
                message="Cannot generate a quote for an empty cart.",
                status_code=400,
            )

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=QUOTE_TTL_MINUTES)

        # Resolve delivery address and state if provided
        resolved_address_id = None
        resolved_delivery_state = None

        if delivery_address_id:
            addr_res = await self.session.execute(
                select(Address).where(Address.id == delivery_address_id)
            )
            address = addr_res.scalar_one_or_none()
            if not address:
                raise AppException(
                    code="ADDRESS_NOT_FOUND",
                    message="Specified delivery address was not found.",
                    status_code=404,
                )
            if cart.customer_id and address.user_id != cart.customer_id:
                raise AppException(
                    code="ADDRESS_NOT_FOUND",
                    message="Specified delivery address was not found.",
                    status_code=404,
                )
            resolved_address_id = address.id
            resolved_delivery_state = validate_state_code(
                address.state, context="Delivery address state"
            )
        elif delivery_state:
            resolved_delivery_state = validate_state_code(
                delivery_state, context="Delivery state"
            )
        elif cart.customer_id:
            addr_res = await self.session.execute(
                select(Address).where(
                    Address.user_id == cart.customer_id,
                    Address.is_default.is_(True),
                )
            )
            default_addr = addr_res.scalar_one_or_none()
            if default_addr:
                resolved_address_id = default_addr.id
                resolved_delivery_state = validate_state_code(
                    default_addr.state, context="Default delivery address state"
                )

        # Fetch live listings with relationships for all cart items
        listing_ids = [item.listing_id for item in cart_items]
        stmt = (
            select(ProductListing)
            .where(ProductListing.id.in_(listing_ids))
            .options(
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.variant).selectinload(
                    ProductVariant.product
                ),
                selectinload(ProductListing.inventory),
            )
        )
        res = await self.session.execute(stmt)
        listings_map = {listing.id: listing for listing in res.scalars().all()}

        # Verify all items exist, are active, have valid tax classifications, and available stock
        for item in cart_items:
            listing = listings_map.get(item.listing_id)
            if not listing or not listing.is_active:
                raise AppException(
                    code="ITEM_UNAVAILABLE",
                    message="One or more items in your basket are no longer active.",
                    status_code=400,
                    details={"listing_id": str(item.listing_id)},
                )
            inv = listing.inventory
            available_qty = (
                max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            )
            if available_qty < item.quantity:
                raise AppException(
                    code="INSUFFICIENT_STOCK",
                    message=f"Insufficient stock for {listing.variant.name if listing.variant else 'item'}. Available: {available_qty}.",
                    status_code=400,
                    details={
                        "listing_id": str(item.listing_id),
                        "requested": item.quantity,
                        "available": available_qty,
                    },
                )

        # Mark existing active quotes for this owner as SUPERSEDED
        if cart.customer_id:
            old_quotes_stmt = select(CheckoutQuote).where(
                CheckoutQuote.customer_id == cart.customer_id,
                CheckoutQuote.status == QuoteStatus.ACTIVE.value,
            )
        else:
            old_quotes_stmt = select(CheckoutQuote).where(
                CheckoutQuote.guest_token_hash == cart.guest_token_hash,
                CheckoutQuote.status == QuoteStatus.ACTIVE.value,
            )
        old_quotes_res = await self.session.execute(old_quotes_stmt)
        for old_q in old_quotes_res.scalars().all():
            old_q.status = QuoteStatus.SUPERSEDED.value

        quote_id = uuid.uuid4()
        quote_items: list[CheckoutQuoteItem] = []
        retailer_subtotals: dict[uuid.UUID, int] = {}
        retailer_info: dict[uuid.UUID, tuple[str, str]] = {}

        total_subtotal_paise = 0
        total_discount_paise = 0
        total_taxable_base_paise = 0
        total_cgst_paise = 0
        total_sgst_paise = 0
        total_igst_paise = 0
        total_tax_paise = 0

        for item in cart_items:
            listing = listings_map[item.listing_id]
            retailer = listing.retailer
            variant = listing.variant
            product = variant.product if variant else None

            # Enforce explicit, valid statutory tax classification (No universal fallback)
            clean_hsn, valid_gst_bps = validate_tax_classification(
                listing.hsn_code,
                listing.gst_rate_basis_points,
                item_identifier=listing.seller_sku or str(listing.id),
            )

            # Enforce valid retailer origin state
            retailer_id = retailer.id
            retailer_name = retailer.name
            retailer_state = validate_state_code(
                retailer.state, context=f"Retailer '{retailer_name}' registered state"
            )
            retailer_info[retailer_id] = (retailer_name, retailer_state)

            unit_orig_price = listing.original_price_paise
            unit_selling_price = listing.selling_price_paise

            # Check applicable discounts
            discounts = (
                await self.discount_service.get_applicable_discounts_for_listing(
                    listing_id=listing.id,
                    selling_price_paise=unit_selling_price,
                )
            )
            unit_discount, unit_discounted_price = (
                self.discount_service.calculate_unit_discount(
                    unit_selling_price, discounts
                )
            )

            line_selling_total = unit_discounted_price * item.quantity
            line_discount_total = unit_discount * item.quantity

            # Tax breakdown per line item
            tax_res = calculate_tax_breakdown(
                selling_price_paise=line_selling_total,
                gst_rate_basis_points=valid_gst_bps,
                retailer_state=retailer_state,
                delivery_state=resolved_delivery_state,
            )

            quote_item = CheckoutQuoteItem(
                id=uuid.uuid4(),
                quote_id=quote_id,
                listing_id=listing.id,
                variant_id=variant.id,
                retailer_id=retailer.id,
                product_title=product.name if product else variant.name,
                variant_title=variant.name,
                sku=listing.seller_sku or variant.sku,
                hsn_code=clean_hsn,
                gst_rate_basis_points=valid_gst_bps,
                quantity=item.quantity,
                unit_original_price_paise=unit_orig_price,
                unit_selling_price_paise=unit_selling_price,
                unit_discount_paise=unit_discount,
                unit_discounted_price_paise=unit_discounted_price,
                total_selling_price_paise=line_selling_total,
                taxable_base_paise=tax_res["taxable_base_paise"],
                cgst_paise=tax_res["cgst_paise"],
                sgst_paise=tax_res["sgst_paise"],
                igst_paise=tax_res["igst_paise"],
                total_tax_paise=tax_res["total_tax_paise"],
                retailer_name=retailer_name,
                retailer_state=retailer_state,
            )
            quote_items.append(quote_item)

            total_subtotal_paise += line_selling_total
            total_discount_paise += line_discount_total
            total_taxable_base_paise += tax_res["taxable_base_paise"]
            total_cgst_paise += tax_res["cgst_paise"]
            total_sgst_paise += tax_res["sgst_paise"]
            total_igst_paise += tax_res["igst_paise"]
            total_tax_paise += tax_res["total_tax_paise"]

            retailer_subtotals[retailer_id] = (
                retailer_subtotals.get(retailer_id, 0) + line_selling_total
            )

        # Calculate per-retailer delivery fees
        total_delivery_fee_paise = 0
        for _r_id, r_subtotal in retailer_subtotals.items():
            fee, _, _ = calculate_retailer_delivery_fee(
                retailer_subtotal_paise=r_subtotal,
                retailer_id=_r_id,
            )
            total_delivery_fee_paise += fee

        total_payable_paise = total_subtotal_paise + total_delivery_fee_paise

        quote = CheckoutQuote(
            id=quote_id,
            customer_id=cart.customer_id,
            guest_token_hash=cart.guest_token_hash,
            cart_id=cart.id,
            delivery_address_id=resolved_address_id,
            delivery_state=resolved_delivery_state,
            subtotal_paise=total_subtotal_paise,
            discount_total_paise=total_discount_paise,
            delivery_fee_paise=total_delivery_fee_paise,
            cgst_paise=total_cgst_paise,
            sgst_paise=total_sgst_paise,
            igst_paise=total_igst_paise,
            total_tax_paise=total_tax_paise,
            total_payable_paise=total_payable_paise,
            currency="INR",
            status=QuoteStatus.ACTIVE.value,
            is_consumed=False,
            expires_at=expires_at,
            items=quote_items,
        )

        self.session.add(quote)
        await self.session.flush()
        return quote

    async def get_quote_by_id(
        self,
        quote_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> CheckoutQuote:
        """Fetch quote by ID and enforce strict ownership security."""
        stmt = (
            select(CheckoutQuote)
            .where(CheckoutQuote.id == quote_id)
            .options(selectinload(CheckoutQuote.items))
        )
        res = await self.session.execute(stmt)
        quote = res.scalar_one_or_none()
        if not quote:
            raise AppException(
                code="QUOTE_NOT_FOUND",
                message="Quote not found.",
                status_code=404,
            )

        # Strict ownership isolation
        if customer_id:
            if quote.customer_id != customer_id:
                raise AppException(
                    code="QUOTE_NOT_FOUND",
                    message="Quote not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if (
                quote.guest_token_hash != guest_token_hash
                or quote.customer_id is not None
            ):
                raise AppException(
                    code="QUOTE_NOT_FOUND",
                    message="Quote not found.",
                    status_code=404,
                )
        else:
            raise AppException(
                code="QUOTE_NOT_FOUND",
                message="Quote not found.",
                status_code=404,
            )

        # Check and update expiry if active
        now = datetime.now(UTC)
        if quote.status == QuoteStatus.ACTIVE.value and quote.expires_at < now:
            quote.status = QuoteStatus.EXPIRED.value

        return quote

    async def validate_quote(
        self,
        quote: CheckoutQuote,
    ) -> QuoteValidationResponse:
        """Inspect quote against current live catalogue and time."""
        now = datetime.now(UTC)
        issues: list[QuoteValidationIssue] = []

        if quote.status == QuoteStatus.EXPIRED.value or quote.expires_at < now:
            quote.status = QuoteStatus.EXPIRED.value
            issues.append(
                QuoteValidationIssue(
                    code="EXPIRED",
                    message="Quote validity window of 15 minutes has elapsed.",
                )
            )

        if quote.status == QuoteStatus.CONSUMED.value:
            issues.append(
                QuoteValidationIssue(
                    code="ALREADY_CONSUMED",
                    message="This quote has already been used in an order.",
                )
            )

        if quote.status == QuoteStatus.SUPERSEDED.value:
            issues.append(
                QuoteValidationIssue(
                    code="SUPERSEDED",
                    message="This quote has been replaced by a more recent quote.",
                )
            )

        # Check live listing status, prices, and tax rates
        listing_ids = [item.listing_id for item in quote.items]
        stmt = (
            select(ProductListing)
            .where(ProductListing.id.in_(listing_ids))
            .options(
                selectinload(ProductListing.inventory),
            )
        )
        res = await self.session.execute(stmt)
        listings_map = {listing.id: listing for listing in res.scalars().all()}

        for item in quote.items:
            listing = listings_map.get(item.listing_id)
            if not listing or not listing.is_active:
                issues.append(
                    QuoteValidationIssue(
                        code="ITEM_UNAVAILABLE",
                        message=f"{item.product_title} is no longer available.",
                        listing_id=item.listing_id,
                    )
                )
                continue

            inv = listing.inventory
            available_qty = (
                max(0, inv.on_hand_quantity - inv.reserved_quantity) if inv else 0
            )
            if available_qty < item.quantity:
                issues.append(
                    QuoteValidationIssue(
                        code="INSUFFICIENT_STOCK",
                        message=f"Stock for {item.product_title} decreased to {available_qty}.",
                        listing_id=item.listing_id,
                        previous_value=item.quantity,
                        current_value=available_qty,
                    )
                )

            if listing.selling_price_paise != item.unit_selling_price_paise:
                issues.append(
                    QuoteValidationIssue(
                        code="PRICE_CHANGED",
                        message=f"Price for {item.product_title} changed from ₹{item.unit_selling_price_paise / 100:.2f} to ₹{listing.selling_price_paise / 100:.2f}.",
                        listing_id=item.listing_id,
                        previous_value=item.unit_selling_price_paise,
                        current_value=listing.selling_price_paise,
                    )
                )

            if not listing.hsn_code or listing.gst_rate_basis_points is None:
                issues.append(
                    QuoteValidationIssue(
                        code="INVALID_TAX_CLASSIFICATION",
                        message=f"{item.product_title} has an unconfigured statutory tax classification.",
                        listing_id=item.listing_id,
                    )
                )
            elif listing.gst_rate_basis_points != item.gst_rate_basis_points:
                issues.append(
                    QuoteValidationIssue(
                        code="TAX_CHANGED",
                        message=f"GST rate for {item.product_title} changed from {item.gst_rate_basis_points / 100:.1f}% to {listing.gst_rate_basis_points / 100:.1f}%.",
                        listing_id=item.listing_id,
                        previous_value=item.gst_rate_basis_points,
                        current_value=listing.gst_rate_basis_points,
                    )
                )

        is_valid = len(issues) == 0
        primary_reason = issues[0].code if issues else None
        message = (
            "Quote is valid and ready for checkout."
            if is_valid
            else f"Quote requires repricing: {issues[0].message}"
        )

        quote_resp = self.format_quote_response(quote)
        return QuoteValidationResponse(
            valid=is_valid,
            reason=primary_reason,
            message=message,
            can_refresh=quote.status != QuoteStatus.CONSUMED.value,
            issues=issues,
            quote=quote_resp,
        )

    async def refresh_quote(
        self,
        old_quote: CheckoutQuote,
        cart: Cart,
    ) -> CheckoutQuote:
        """Regenerate an expired or superseded quote, linking the previous quote."""
        if old_quote.status == QuoteStatus.CONSUMED.value:
            raise AppException(
                code="QUOTE_ALREADY_CONSUMED",
                message="Cannot refresh an already consumed quote.",
                status_code=400,
            )

        new_quote = await self.generate_quote_from_cart(
            cart=cart,
            delivery_address_id=old_quote.delivery_address_id,
            delivery_state=old_quote.delivery_state,
        )

        old_quote.status = QuoteStatus.SUPERSEDED.value
        old_quote.superseded_by_quote_id = new_quote.id
        await self.session.flush()

        return new_quote

    async def list_customer_quotes(
        self,
        customer_id: uuid.UUID,
        limit: int = 10,
    ) -> list[CheckoutQuote]:
        """List customer's quote history."""
        stmt = (
            select(CheckoutQuote)
            .where(CheckoutQuote.customer_id == customer_id)
            .options(selectinload(CheckoutQuote.items))
            .order_by(desc(CheckoutQuote.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    def format_quote_response(quote: CheckoutQuote) -> QuoteResponse:
        """Format ORM CheckoutQuote into Pydantic QuoteResponse schema."""
        retailer_totals: dict[uuid.UUID, int] = {}
        retailer_info: dict[uuid.UUID, tuple[str, str]] = {}

        for item in quote.items:
            retailer_totals[item.retailer_id] = (
                retailer_totals.get(item.retailer_id, 0)
                + item.total_selling_price_paise
            )
            retailer_info[item.retailer_id] = (item.retailer_name, item.retailer_state)

        retailer_breakdowns: list[RetailerPricingBreakdownSchema] = []
        for r_id, r_subtotal in retailer_totals.items():
            r_name, r_state = retailer_info[r_id]
            fee, qualifies, deficit = calculate_retailer_delivery_fee(
                retailer_subtotal_paise=r_subtotal,
                retailer_id=r_id,
            )
            retailer_breakdowns.append(
                RetailerPricingBreakdownSchema(
                    retailer_id=r_id,
                    retailer_name=r_name,
                    retailer_state=r_state,
                    subtotal_paise=r_subtotal,
                    delivery_fee_paise=fee,
                    free_delivery_threshold_paise=settings.DEFAULT_FREE_DELIVERY_THRESHOLD_PAISE,
                    qualifies_for_free_delivery=qualifies,
                    amount_needed_for_free_delivery_paise=deficit,
                )
            )

        return QuoteResponse.model_validate(
            {
                "id": quote.id,
                "customer_id": quote.customer_id,
                "cart_id": quote.cart_id,
                "delivery_address_id": quote.delivery_address_id,
                "delivery_state": quote.delivery_state,
                "subtotal_paise": quote.subtotal_paise,
                "discount_total_paise": quote.discount_total_paise,
                "delivery_fee_paise": quote.delivery_fee_paise,
                "cgst_paise": quote.cgst_paise,
                "sgst_paise": quote.sgst_paise,
                "igst_paise": quote.igst_paise,
                "total_tax_paise": quote.total_tax_paise,
                "total_payable_paise": quote.total_payable_paise,
                "currency": quote.currency,
                "status": quote.status,
                "is_consumed": quote.is_consumed,
                "consumed_at": quote.consumed_at,
                "expires_at": quote.expires_at,
                "superseded_by_quote_id": quote.superseded_by_quote_id,
                "created_at": quote.created_at,
                "updated_at": quote.updated_at,
                "items": quote.items,
                "retailer_breakdowns": retailer_breakdowns,
            }
        )
