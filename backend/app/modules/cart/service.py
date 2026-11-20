import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.cart.schemas import (
    CartItemResponse,
    CartResponse,
    CartRetailerSummary,
)


def generate_guest_token() -> str:
    return secrets.token_urlsafe(32)


def hash_guest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CartRepository(session)

    async def get_or_create_cart(
        self,
        customer_id: uuid.UUID | None = None,
        guest_token: str | None = None,
    ) -> tuple[Cart, str | None, bool]:
        """
        Resolves or creates the active cart.
        Returns (cart, effective_guest_token, is_new_guest_token).
        """
        now = datetime.now(UTC)

        # 1. Authenticated customer
        if customer_id:
            cart = await self.repo.get_active_cart_by_customer_id(customer_id)
            if not cart:
                cart = await self.repo.create_cart(customer_id=customer_id)
                await self.session.commit()
                cart = await self.repo.get_cart_by_id(cart.id)
            return cart, None, False

        # 2. Guest customer with token
        if guest_token:
            token_hash = hash_guest_token(guest_token)
            cart = await self.repo.get_active_cart_by_guest_token_hash(token_hash)
            if cart:
                # Check expiration
                if cart.expires_at and cart.expires_at < now:
                    cart.status = "ABANDONED"
                    await self.session.commit()
                else:
                    return cart, guest_token, False

        # 3. Create new guest cart
        new_token = generate_guest_token()
        new_hash = hash_guest_token(new_token)
        expires_at = now + timedelta(days=30)
        cart = await self.repo.create_cart(
            guest_token_hash=new_hash,
            expires_at=expires_at,
        )
        await self.session.commit()
        cart = await self.repo.get_cart_by_id(cart.id)
        return cart, new_token, True

    def format_cart_response(
        self,
        cart: Cart,
        items: list[CartItem],
        additional_warnings: list[str] | None = None,
    ) -> CartResponse:
        """Dynamically computes prices, availability, and summaries from catalogue data."""
        items_responses: list[CartItemResponse] = []
        warnings: list[str] = list(additional_warnings or [])
        retailers_map: dict[uuid.UUID, dict] = {}

        total_quantity = 0
        subtotal_paise = 0

        for item in items:
            listing = item.listing
            variant = item.variant
            product = variant.product if variant else None
            retailer = item.retailer

            # Inventory check
            inv = listing.inventory if listing else None
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)

            # Active status check across all parent entities
            is_active = (
                listing is not None
                and listing.is_active
                and variant is not None
                and variant.is_active
                and product is not None
                and product.is_active
                and retailer is not None
                and retailer.is_active
            )

            # Availability flag & message
            is_available = is_active and (available_stock >= item.quantity)
            val_msg: str | None = None
            prod_name = product.name if product else "Product"

            if not is_active:
                val_msg = "This item is no longer available"
                warnings.append(f"'{prod_name}' is currently unavailable.")
            elif available_stock <= 0:
                val_msg = "Out of stock"
                warnings.append(f"'{prod_name}' is out of stock.")
            elif available_stock < item.quantity:
                val_msg = f"Only {available_stock} units available in stock"
                warnings.append(
                    f"'{prod_name}' only has {available_stock} units left in stock."
                )

            # Dynamic price
            unit_price = listing.selling_price_paise if listing else 0
            item_subtotal = unit_price * item.quantity

            # Primary image
            primary_img = None
            if product and product.images:
                for img in product.images:
                    if img.is_primary:
                        primary_img = img.url
                        break
                if not primary_img and len(product.images) > 0:
                    primary_img = product.images[0].url

            item_resp = CartItemResponse(
                id=item.id,
                listing_id=item.listing_id,
                variant_id=item.variant_id,
                product_id=product.id if product else uuid.uuid4(),
                product_name=prod_name,
                product_slug=product.slug if product else "",
                variant_name=variant.name if variant else None,
                attributes=variant.attributes if variant else {},
                primary_image_url=primary_img,
                retailer_id=retailer.id if retailer else uuid.uuid4(),
                retailer_name=retailer.name if retailer else "Unknown Retailer",
                retailer_rating=retailer.rating if retailer else None,
                unit_price_paise=unit_price,
                quantity=item.quantity,
                subtotal_paise=item_subtotal,
                available_stock=available_stock,
                is_available=is_available,
                validation_message=val_msg,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            items_responses.append(item_resp)

            total_quantity += item.quantity
            subtotal_paise += item_subtotal

            # Group by retailer
            r_id = retailer.id if retailer else uuid.uuid4()
            r_name = retailer.name if retailer else "Unknown Retailer"
            if r_id not in retailers_map:
                retailers_map[r_id] = {
                    "retailer_id": r_id,
                    "retailer_name": r_name,
                    "item_count": 0,
                    "subtotal_paise": 0,
                }
            retailers_map[r_id]["item_count"] += 1
            retailers_map[r_id]["subtotal_paise"] += item_subtotal

        # Retailer summaries
        retailer_summaries = [
            CartRetailerSummary(**data)
            for data in sorted(retailers_map.values(), key=lambda r: r["retailer_name"])
        ]

        return CartResponse(
            id=cart.id,
            status=cart.status,
            currency=cart.currency,
            items=items_responses,
            item_count=len(items_responses),
            total_quantity=total_quantity,
            subtotal_paise=subtotal_paise,
            retailers=retailer_summaries,
            warnings=warnings,
            created_at=cart.created_at,
            updated_at=cart.updated_at,
        )

    async def get_cart(self, cart_id: uuid.UUID) -> CartResponse:
        cart = await self.repo.get_cart_by_id(cart_id)
        if not cart:
            raise AppException(
                code="CART_NOT_FOUND", message="Cart not found.", status_code=404
            )
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items)

    async def add_item(
        self, cart_id: uuid.UUID, listing_id: uuid.UUID, quantity: int
    ) -> CartResponse:
        if quantity < 1 or quantity > 10:
            raise AppException(
                code="INVALID_QUANTITY",
                message="Quantity must be between 1 and 10.",
                status_code=400,
            )

        # Lock cart row
        cart = await self.repo.get_cart_by_id(cart_id, for_update=True)
        if not cart or cart.status != "ACTIVE":
            raise AppException(
                code="CART_NOT_FOUND",
                message="Active cart not found.",
                status_code=404,
            )

        # Validate listing & stock
        listing = await self.repo.get_listing_with_details(listing_id)
        if (
            not listing
            or not listing.is_active
            or not listing.variant.is_active
            or not listing.variant.product.is_active
            or not listing.retailer.is_active
        ):
            raise AppException(
                code="ITEM_UNAVAILABLE",
                message="The requested product listing is not currently available for purchase.",
                status_code=400,
            )

        inv = listing.inventory
        on_hand = inv.on_hand_quantity if inv else 0
        reserved = inv.reserved_quantity if inv else 0
        available_stock = max(0, on_hand - reserved)

        if available_stock <= 0:
            raise AppException(
                code="OUT_OF_STOCK",
                message="This product is currently out of stock.",
                status_code=400,
            )

        # Check existing item
        existing_item = await self.repo.get_cart_item(
            cart_id, listing_id, for_update=True
        )
        if existing_item:
            target_quantity = existing_item.quantity + quantity
            if target_quantity > 10:
                raise AppException(
                    code="MAX_QUANTITY_EXCEEDED",
                    message="You cannot have more than 10 units of an item in your cart.",
                    status_code=400,
                )
            if target_quantity > available_stock:
                raise AppException(
                    code="INSUFFICIENT_STOCK",
                    message=f"Only {available_stock} units available in stock.",
                    status_code=400,
                )
            await self.repo.update_cart_item_quantity(existing_item, target_quantity)
        else:
            if quantity > available_stock:
                raise AppException(
                    code="INSUFFICIENT_STOCK",
                    message=f"Only {available_stock} units available in stock.",
                    status_code=400,
                )
            await self.repo.add_cart_item(
                cart_id=cart_id,
                listing_id=listing_id,
                variant_id=listing.variant_id,
                retailer_id=listing.retailer_id,
                quantity=quantity,
            )

        await self.session.commit()
        cart = await self.repo.get_cart_by_id(cart_id)
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items)

    async def update_item_quantity(
        self, cart_id: uuid.UUID, item_id: uuid.UUID, quantity: int
    ) -> CartResponse:
        if quantity < 1 or quantity > 10:
            raise AppException(
                code="INVALID_QUANTITY",
                message="Quantity must be between 1 and 10.",
                status_code=400,
            )

        cart = await self.repo.get_cart_by_id(cart_id, for_update=True)
        if not cart or cart.status != "ACTIVE":
            raise AppException(
                code="CART_NOT_FOUND",
                message="Active cart not found.",
                status_code=404,
            )

        item = await self.repo.get_cart_item_by_id(item_id, for_update=True)
        if not item or item.cart_id != cart_id:
            raise AppException(
                code="ITEM_NOT_FOUND",
                message="Cart item not found.",
                status_code=404,
            )

        listing = await self.repo.get_listing_with_details(item.listing_id)
        if not listing:
            raise AppException(
                code="ITEM_UNAVAILABLE",
                message="Item listing no longer exists.",
                status_code=400,
            )

        inv = listing.inventory
        on_hand = inv.on_hand_quantity if inv else 0
        reserved = inv.reserved_quantity if inv else 0
        available_stock = max(0, on_hand - reserved)

        if quantity > available_stock:
            raise AppException(
                code="INSUFFICIENT_STOCK",
                message=f"Only {available_stock} units available in stock.",
                status_code=400,
            )

        await self.repo.update_cart_item_quantity(item, quantity)
        await self.session.commit()

        cart = await self.repo.get_cart_by_id(cart_id)
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items)

    async def remove_item(self, cart_id: uuid.UUID, item_id: uuid.UUID) -> CartResponse:
        cart = await self.repo.get_cart_by_id(cart_id, for_update=True)
        if not cart or cart.status != "ACTIVE":
            raise AppException(
                code="CART_NOT_FOUND",
                message="Active cart not found.",
                status_code=404,
            )

        item = await self.repo.get_cart_item_by_id(item_id, for_update=True)
        if not item or item.cart_id != cart_id:
            raise AppException(
                code="ITEM_NOT_FOUND",
                message="Cart item not found.",
                status_code=404,
            )

        await self.repo.remove_cart_item(item)
        await self.session.commit()

        cart = await self.repo.get_cart_by_id(cart_id)
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items)

    async def clear_cart(self, cart_id: uuid.UUID) -> CartResponse:
        cart = await self.repo.get_cart_by_id(cart_id, for_update=True)
        if not cart or cart.status != "ACTIVE":
            raise AppException(
                code="CART_NOT_FOUND",
                message="Active cart not found.",
                status_code=404,
            )

        await self.repo.clear_cart(cart_id)
        await self.session.commit()

        cart = await self.repo.get_cart_by_id(cart_id)
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items)

    async def _supersede_active_quotes(self, cart: Cart) -> None:
        """Mark all active checkout quotes for this cart's owner as SUPERSEDED."""
        from app.modules.pricing.models import CheckoutQuote, QuoteStatus

        if cart.customer_id:
            stmt = select(CheckoutQuote).where(
                CheckoutQuote.customer_id == cart.customer_id,
                CheckoutQuote.status == QuoteStatus.ACTIVE.value,
            )
        elif cart.guest_token_hash:
            stmt = select(CheckoutQuote).where(
                CheckoutQuote.guest_token_hash == cart.guest_token_hash,
                CheckoutQuote.status == QuoteStatus.ACTIVE.value,
            )
        else:
            return

        res = await self.session.execute(stmt)
        for q in res.scalars().all():
            q.status = QuoteStatus.SUPERSEDED.value

    async def replace_item(
        self,
        cart_id: uuid.UUID,
        item_id: uuid.UUID,
        new_listing_id: uuid.UUID,
        quantity: int | None = None,
    ) -> tuple[CartResponse, uuid.UUID, uuid.UUID]:
        """
        Replaces a cart item with an alternative listing.
        Enforces:
        - Cart is active
        - Caller owns the item
        - Substitute listing is active, from a verified active retailer, and in stock
        - Substitute belongs to the exact same category
        - Preserves quantity if possible, otherwise clamps to available stock (max 10)
        - Handles merging if substitute is already present in cart
        - Supersedes active checkout quotes
        """
        cart = await self.repo.get_cart_by_id(cart_id, for_update=True)
        if not cart or cart.status != "ACTIVE":
            raise AppException(
                code="CART_NOT_FOUND",
                message="Active cart not found.",
                status_code=404,
            )

        item = await self.repo.get_cart_item_by_id(item_id, for_update=True)
        if not item or item.cart_id != cart_id:
            raise AppException(
                code="ITEM_NOT_FOUND",
                message="Cart item not found.",
                status_code=404,
            )

        # 1. Fetch current listing to check category
        current_listing = await self.repo.get_listing_with_details(item.listing_id)
        if not current_listing:
            raise AppException(
                code="ITEM_UNAVAILABLE",
                message="Original cart item listing not found.",
                status_code=400,
            )

        # 2. Fetch target substitute listing with details
        new_listing = await self.repo.get_listing_with_details(new_listing_id)
        if not new_listing:
            raise AppException(
                code="LISTING_NOT_FOUND",
                message="Substitute listing not found.",
                status_code=404,
            )

        # 3. Check active & verified
        if (
            not new_listing.is_active
            or not new_listing.variant.is_active
            or not new_listing.variant.product.is_active
            or not new_listing.retailer.is_active
            or new_listing.retailer.verification_status != "VERIFIED"
        ):
            raise AppException(
                code="ALTERNATIVE_NOT_AVAILABLE",
                message="The selected substitute is not currently available for purchase.",
                status_code=400,
            )

        # 4. Enforce strict category match
        curr_cat_id = current_listing.variant.product.category_id
        new_cat_id = new_listing.variant.product.category_id
        if curr_cat_id != new_cat_id:
            raise AppException(
                code="CATEGORY_MISMATCH",
                message="Substitute product must belong to the same category.",
                status_code=400,
            )

        # 5. Check inventory
        inv = new_listing.inventory
        on_hand = inv.on_hand_quantity if inv else 0
        reserved = inv.reserved_quantity if inv else 0
        available_stock = max(0, on_hand - reserved)

        if available_stock <= 0:
            raise AppException(
                code="OUT_OF_STOCK",
                message="The selected substitute is currently out of stock.",
                status_code=400,
            )

        # 6. Determine quantity
        target_qty = quantity if quantity is not None else item.quantity
        if target_qty < 1:
            target_qty = 1
        if target_qty > 10:
            target_qty = 10
        if target_qty > available_stock:
            target_qty = available_stock

        # 7. Check if target listing is already in cart under another item
        existing_target_item = await self.repo.get_cart_item(
            cart_id, new_listing_id, for_update=True
        )

        if existing_target_item and existing_target_item.id != item.id:
            # Combine quantity up to available_stock and max 10
            combined_qty = min(
                10,
                min(available_stock, existing_target_item.quantity + target_qty),
            )
            existing_target_item.quantity = combined_qty
            await self.repo.remove_cart_item(item)
            active_item_id = existing_target_item.id
        else:
            item.listing_id = new_listing_id
            item.variant_id = new_listing.variant_id
            item.retailer_id = new_listing.retailer_id
            item.quantity = target_qty
            active_item_id = item.id

        # 8. Supersede active quotes
        await self._supersede_active_quotes(cart)

        await self.session.commit()

        cart = await self.repo.get_cart_by_id(cart_id)
        items = await self.repo.get_cart_items(cart_id)
        return self.format_cart_response(cart, items), item_id, active_item_id

    async def merge_guest_cart(
        self, customer_id: uuid.UUID, guest_token: str | None
    ) -> tuple[CartResponse, int, list[str]]:
        """
        Atomically merges guest cart into the customer's active cart.
        Resolves conflicts by combining quantities up to stock and max limit 10.
        Marks guest cart as MERGED.
        """
        # Ensure customer cart exists
        user_cart = await self.repo.get_active_cart_by_customer_id(
            customer_id, for_update=True
        )
        if not user_cart:
            user_cart = await self.repo.create_cart(customer_id=customer_id)
            await self.session.flush()

        if not guest_token:
            user_cart = await self.repo.get_cart_by_id(user_cart.id)
            items = await self.repo.get_cart_items(user_cart.id)
            return self.format_cart_response(user_cart, items), 0, []

        token_hash = hash_guest_token(guest_token)
        guest_cart = await self.repo.get_active_cart_by_guest_token_hash(
            token_hash, for_update=True
        )

        if not guest_cart or guest_cart.status != "ACTIVE":
            user_cart = await self.repo.get_cart_by_id(user_cart.id)
            items = await self.repo.get_cart_items(user_cart.id)
            return self.format_cart_response(user_cart, items), 0, []

        warnings: list[str] = []
        migrated_count = 0
        guest_items = await self.repo.get_cart_items(guest_cart.id)

        for guest_item in guest_items:
            listing = await self.repo.get_listing_with_details(guest_item.listing_id)
            if not listing:
                continue

            # Check stock
            inv = listing.inventory
            on_hand = inv.on_hand_quantity if inv else 0
            reserved = inv.reserved_quantity if inv else 0
            available_stock = max(0, on_hand - reserved)
            prod_name = (
                listing.variant.product.name
                if listing.variant and listing.variant.product
                else "Item"
            )

            is_active = (
                listing.is_active
                and listing.variant.is_active
                and listing.variant.product.is_active
                and listing.retailer.is_active
            )

            if not is_active:
                warnings.append(
                    f"'{prod_name}' is no longer active and was not migrated."
                )
                continue

            if available_stock <= 0:
                warnings.append(f"'{prod_name}' is out of stock and was not migrated.")
                continue

            # Check if user cart already has this listing
            existing_user_item = await self.repo.get_cart_item(
                user_cart.id, guest_item.listing_id, for_update=True
            )

            if existing_user_item:
                combined_qty = existing_user_item.quantity + guest_item.quantity
                capped_qty = min(combined_qty, 10, available_stock)
                if capped_qty < combined_qty:
                    warnings.append(
                        f"Quantity for '{prod_name}' was capped at {capped_qty} due to limits/stock."
                    )
                await self.repo.update_cart_item_quantity(
                    existing_user_item, capped_qty
                )
                migrated_count += 1
            else:
                capped_qty = min(guest_item.quantity, 10, available_stock)
                if capped_qty < guest_item.quantity:
                    warnings.append(
                        f"Quantity for '{prod_name}' was capped at {capped_qty} due to limits/stock."
                    )
                await self.repo.add_cart_item(
                    cart_id=user_cart.id,
                    listing_id=guest_item.listing_id,
                    variant_id=guest_item.variant_id,
                    retailer_id=guest_item.retailer_id,
                    quantity=capped_qty,
                )
                migrated_count += 1

        # Mark guest cart as merged
        await self.repo.mark_cart_merged(guest_cart)
        await self.session.commit()

        # Reload customer cart & items
        user_cart = await self.repo.get_cart_by_id(user_cart.id)
        items = await self.repo.get_cart_items(user_cart.id)
        return (
            self.format_cart_response(user_cart, items, additional_warnings=warnings),
            migrated_count,
            warnings,
        )
