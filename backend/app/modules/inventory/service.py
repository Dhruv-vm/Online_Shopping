import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.modules.inventory.models import (
    InventoryReservation,
    InventoryReservationItem,
    ReservationStatus,
)
from app.modules.inventory.repository import ReservationRepository
from app.modules.pricing.models import QuoteStatus
from app.modules.pricing.quote_service import QuoteService


class ReservationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReservationRepository(session)
        self.quote_service = QuoteService(session)

    async def create_reservation_from_quote(
        self,
        quote_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        idempotency_key: str | None = None,
    ) -> InventoryReservation:
        """Atomically reserves stock for all items in an active checkout quote.

        Guarantees:
        - Deterministic lock ordering on store_inventory rows to prevent deadlocks.
        - All-or-nothing atomicity across multiple retailers and listings.
        - Strict validation of quote active status and expiry.
        - Idempotency support.
        - Never over-reserves or produces negative stock.
        """
        # 1. Check idempotency if key provided
        if idempotency_key:
            existing = await self.repo.get_by_idempotency(
                customer_id=customer_id,
                guest_token_hash=guest_token_hash,
                idempotency_key=idempotency_key,
            )
            if existing:
                # Disallow key reuse across different quotes
                if existing.quote_id != quote_id:
                    raise AppException(
                        code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                        message="This idempotency key has already been used with a different quote payload.",
                        status_code=409,
                    )

                now = datetime.now(UTC)
                exp = existing.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=UTC)

                if existing.status == ReservationStatus.ACTIVE.value and exp > now:
                    return existing
                elif existing.status == ReservationStatus.CONFIRMED.value:
                    return existing
                else:  # EXPIRED, RELEASED, or past TTL
                    effective_status = (
                        ReservationStatus.EXPIRED.value
                        if (
                            existing.status == ReservationStatus.ACTIVE.value
                            and exp <= now
                        )
                        else existing.status
                    )
                    raise AppException(
                        code="IDEMPOTENCY_KEY_ALREADY_USED",
                        message=(
                            f"This idempotency key was already used for a reservation in '{effective_status}' status. "
                            "Replaying a spent idempotency key to create a new reservation is prohibited. "
                            "Please generate a new idempotency key."
                        ),
                        status_code=409,
                    )

        # 2. Fetch and strictly validate quote ownership and status
        quote = await self.quote_service.get_quote_by_id(
            quote_id=quote_id,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
        )

        now = datetime.now(UTC)
        quote_exp = quote.expires_at
        if quote_exp.tzinfo is None:
            quote_exp = quote_exp.replace(tzinfo=UTC)

        if quote.status == QuoteStatus.EXPIRED.value or quote_exp < now:
            quote.status = QuoteStatus.EXPIRED.value
            raise AppException(
                code="QUOTE_EXPIRED",
                message="Quote validity has elapsed. Please refresh your quote before reserving inventory.",
                status_code=409,
            )

        if quote.status == QuoteStatus.CONSUMED.value or quote.is_consumed:
            raise AppException(
                code="QUOTE_CONSUMED",
                message="This quote has already been consumed.",
                status_code=409,
            )

        if quote.status == QuoteStatus.SUPERSEDED.value:
            raise AppException(
                code="QUOTE_SUPERSEDED",
                message="This quote has been replaced by a newer quote. Please use the latest quote.",
                status_code=409,
            )

        if not quote.items:
            raise AppException(
                code="EMPTY_QUOTE",
                message="Cannot reserve inventory for an empty quote.",
                status_code=400,
            )

        # 3. Check for existing active reservation on this quote
        existing_res = await self.repo.get_active_by_quote_id(quote.id)
        if existing_res:
            res_exp = existing_res.expires_at
            if res_exp.tzinfo is None:
                res_exp = res_exp.replace(tzinfo=UTC)
            if res_exp > now:
                return existing_res
            else:
                # Expired active reservation on this quote; release it before creating fresh
                await self.release_reservation(
                    reservation_id=existing_res.id,
                    customer_id=customer_id,
                    guest_token_hash=guest_token_hash,
                    reason="TTL_EXPIRED",
                    internal=True,
                )

        # 4. Acquire row-level write locks in deterministic ascending order of listing_id
        listing_ids = [item.listing_id for item in quote.items]
        inventories = await self.repo.lock_inventories_for_update(listing_ids)

        # Aggregate requested quantity per listing_id to handle any duplicate listings safely
        requested_by_listing: dict[uuid.UUID, int] = {}
        items_by_listing: dict[uuid.UUID, Any] = {}
        for item in quote.items:
            requested_by_listing[item.listing_id] = (
                requested_by_listing.get(item.listing_id, 0) + item.quantity
            )
            items_by_listing[item.listing_id] = item

        # 5. Verify availability and listing invariants atomically
        shortages = []
        for listing_id, total_quantity in requested_by_listing.items():
            inv = inventories.get(listing_id)
            item = items_by_listing[listing_id]
            if not inv:
                shortages.append(
                    {
                        "listing_id": str(listing_id),
                        "product_title": item.product_title,
                        "requested_quantity": total_quantity,
                        "available_quantity": 0,
                        "message": f"Inventory record not found for {item.product_title}.",
                    }
                )
                continue

            # Invariant check: Listing must belong to stated retailer and variant
            if inv.listing:
                if inv.listing.retailer_id != item.retailer_id:
                    raise AppException(
                        code="INVALID_RETAILER_LISTING_MISMATCH",
                        message=f"Listing {listing_id} does not belong to retailer {item.retailer_id}.",
                        status_code=400,
                    )
                if inv.listing.variant_id != item.variant_id:
                    raise AppException(
                        code="INVALID_VARIANT_LISTING_MISMATCH",
                        message=f"Listing {listing_id} does not belong to variant {item.variant_id}.",
                        status_code=400,
                    )

            available = inv.on_hand_quantity - inv.reserved_quantity
            if available < total_quantity:
                shortages.append(
                    {
                        "listing_id": str(listing_id),
                        "product_title": item.product_title,
                        "requested_quantity": total_quantity,
                        "available_quantity": max(0, available),
                        "message": f"Insufficient stock for {item.product_title}. Requested {total_quantity}, but only {max(0, available)} available.",
                    }
                )

        if shortages:
            # All-or-nothing rollback: raise 409 without mutating any inventory counters
            raise AppException(
                code="INSUFFICIENT_STOCK",
                message="One or more items do not have sufficient stock.",
                status_code=409,
                details=shortages,
            )

        # 6. All items verified: atomically increment reserved_quantity
        for listing_id, total_quantity in requested_by_listing.items():
            inv = inventories[listing_id]
            inv.reserved_quantity += total_quantity

        expires_at = now + timedelta(minutes=settings.RESERVATION_TTL_MINUTES)
        reservation_id = uuid.uuid4()

        reservation = InventoryReservation(
            id=reservation_id,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            quote_id=quote.id,
            status=ReservationStatus.ACTIVE.value,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
            items=[
                InventoryReservationItem(
                    id=uuid.uuid4(),
                    reservation_id=reservation_id,
                    listing_id=listing_id,
                    retailer_id=items_by_listing[listing_id].retailer_id,
                    variant_id=items_by_listing[listing_id].variant_id,
                    quantity=total_qty,
                )
                for listing_id, total_qty in requested_by_listing.items()
            ],
        )

        quote_id_val = quote.id
        self.session.add(reservation)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            # Handle concurrent creation race:
            # 1. Active reservation for quote already created by another transaction
            existing_active = await self.repo.get_active_by_quote_id(quote_id_val)
            if existing_active:
                return existing_active
            # 2. Reservation for this idempotency key already created by another transaction
            if idempotency_key:
                existing_idem = await self.repo.get_by_idempotency(
                    customer_id=customer_id,
                    guest_token_hash=guest_token_hash,
                    idempotency_key=idempotency_key,
                )
                if (
                    existing_idem
                    and existing_idem.status == ReservationStatus.ACTIVE.value
                ):
                    return existing_idem
            raise AppException(
                code="CONCURRENT_RESERVATION_CONFLICT",
                message="A conflicting reservation is currently being processed. Please retry.",
                status_code=409,
            ) from None
        return reservation

    async def allocate_reservation_to_order(
        self,
        reservation_id: uuid.UUID,
        order_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        internal: bool = False,
    ) -> InventoryReservation:
        """Transitions ACTIVE reservation to ALLOCATED_TO_ORDER and links order_id."""
        res = await self.repo.lock_reservation_for_update(reservation_id)
        if not res:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Reservation was not found.",
                status_code=404,
            )

        if not internal:
            if customer_id:
                if res.customer_id != customer_id:
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            elif guest_token_hash:
                if (
                    res.guest_token_hash != guest_token_hash
                    or res.customer_id is not None
                ):
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            else:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Reservation was not found.",
                    status_code=404,
                )

        if res.status == ReservationStatus.CONFIRMED.value:
            raise AppException(
                code="RESERVATION_ALREADY_CONFIRMED",
                message="Cannot allocate a confirmed reservation.",
                status_code=409,
            )

        if res.status == ReservationStatus.EXPIRED.value:
            raise AppException(
                code="RESERVATION_EXPIRED",
                message="Cannot allocate an expired reservation.",
                status_code=409,
            )

        if res.status == ReservationStatus.RELEASED.value:
            raise AppException(
                code="RESERVATION_RELEASED",
                message="Cannot allocate a released reservation.",
                status_code=409,
            )

        # Check TTL
        now = datetime.now(UTC)
        exp = res.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < now:
            await self.release_reservation(
                reservation_id=res.id,
                reason="TTL_EXPIRED",
                internal=True,
            )
            raise AppException(
                code="RESERVATION_EXPIRED",
                message="Reservation has expired.",
                status_code=409,
            )

        res.status = ReservationStatus.ALLOCATED_TO_ORDER.value
        res.order_id = order_id
        await self.session.flush()
        return res

    async def get_reservation(
        self,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> InventoryReservation:
        """Fetch reservation and enforce ownership isolation. Handles on-demand expiry."""
        res = await self.repo.get_by_id(reservation_id)
        if not res:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Reservation was not found.",
                status_code=404,
            )

        # Strict caller ownership check
        if customer_id:
            if res.customer_id != customer_id:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Reservation was not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if res.guest_token_hash != guest_token_hash or res.customer_id is not None:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Reservation was not found.",
                    status_code=404,
                )
        else:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Reservation was not found.",
                status_code=404,
            )

        # Auto-expire if past TTL
        now = datetime.now(UTC)
        exp = res.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)

        if res.status == ReservationStatus.ACTIVE.value and exp < now:
            await self.release_reservation(
                reservation_id=res.id,
                customer_id=customer_id,
                guest_token_hash=guest_token_hash,
                reason="TTL_EXPIRED",
                internal=True,
            )
            res.status = ReservationStatus.EXPIRED.value

        return res

    async def release_reservation(
        self,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        reason: str = "USER_RELEASED",
        internal: bool = False,
    ) -> InventoryReservation:
        """Explicitly or automatically releases held reserved stock."""
        res = await self.repo.lock_reservation_for_update(reservation_id)
        if not res:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Reservation was not found.",
                status_code=404,
            )

        # Strict ownership validation if not an internal system operation
        if not internal:
            if customer_id:
                if res.customer_id != customer_id:
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            elif guest_token_hash:
                if (
                    res.guest_token_hash != guest_token_hash
                    or res.customer_id is not None
                ):
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            else:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Reservation was not found.",
                    status_code=404,
                )

        if res.status == ReservationStatus.CONFIRMED.value:
            raise AppException(
                code="RESERVATION_ALREADY_CONFIRMED",
                message="Cannot release a confirmed reservation.",
                status_code=409,
            )

        if res.status in (
            ReservationStatus.RELEASED.value,
            ReservationStatus.EXPIRED.value,
        ):
            return res  # Already released, idempotent

        # Acquire row write locks on inventory rows in sorted order
        listing_ids = [item.listing_id for item in res.items]
        inventories = await self.repo.lock_inventories_for_update(listing_ids)

        # Aggregate release quantities per listing
        released_by_listing: dict[uuid.UUID, int] = {}
        for item in res.items:
            released_by_listing[item.listing_id] = (
                released_by_listing.get(item.listing_id, 0) + item.quantity
            )

        for listing_id, total_qty in released_by_listing.items():
            inv = inventories.get(listing_id)
            if inv:
                inv.reserved_quantity = max(0, inv.reserved_quantity - total_qty)

        target_status = (
            ReservationStatus.EXPIRED.value
            if reason == "TTL_EXPIRED"
            else ReservationStatus.RELEASED.value
        )
        res.status = target_status
        res.released_at = datetime.now(UTC)
        res.release_reason = reason

        await self.session.flush()
        return res

    async def confirm_reservation(
        self,
        reservation_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        internal: bool = False,
    ) -> InventoryReservation:
        """Transitions ACTIVE reservation to CONFIRMED. Permanently reduces on_hand stock."""
        res = await self.repo.lock_reservation_for_update(reservation_id)
        if not res:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Reservation was not found.",
                status_code=404,
            )

        if not internal:
            if customer_id:
                if res.customer_id != customer_id:
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            elif guest_token_hash:
                if (
                    res.guest_token_hash != guest_token_hash
                    or res.customer_id is not None
                ):
                    raise AppException(
                        code="RESERVATION_NOT_FOUND",
                        message="Reservation was not found.",
                        status_code=404,
                    )
            else:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Reservation was not found.",
                    status_code=404,
                )

        if res.status == ReservationStatus.CONFIRMED.value:
            return res  # Idempotent confirmation

        if res.status == ReservationStatus.EXPIRED.value:
            raise AppException(
                code="RESERVATION_EXPIRED",
                message="Cannot confirm an expired reservation.",
                status_code=409,
            )

        if res.status == ReservationStatus.RELEASED.value:
            raise AppException(
                code="RESERVATION_RELEASED",
                message="Cannot confirm a released reservation.",
                status_code=409,
            )

        # Lock inventory rows in sorted order and convert reserved quantity to actual deduction
        listing_ids = [item.listing_id for item in res.items]
        inventories = await self.repo.lock_inventories_for_update(listing_ids)

        # Aggregate confirmation deductions per listing
        deducted_by_listing: dict[uuid.UUID, int] = {}
        for item in res.items:
            deducted_by_listing[item.listing_id] = (
                deducted_by_listing.get(item.listing_id, 0) + item.quantity
            )

        for listing_id, total_qty in deducted_by_listing.items():
            inv = inventories.get(listing_id)
            if inv:
                inv.on_hand_quantity = max(0, inv.on_hand_quantity - total_qty)
                inv.reserved_quantity = max(0, inv.reserved_quantity - total_qty)

        res.status = ReservationStatus.CONFIRMED.value
        res.confirmed_at = datetime.now(UTC)

        await self.session.flush()
        return res

    async def cleanup_expired_reservations(self, limit: int = 100) -> int:
        """Background cleanup job to expire reservations past their TTL and release stock."""
        expired_active = await self.repo.get_expired_active_reservations(limit=limit)
        count = 0
        for res in expired_active:
            try:
                await self.release_reservation(
                    reservation_id=res.id,
                    reason="TTL_EXPIRED",
                    internal=True,
                )
                count += 1
            except Exception:
                # Concurrent update or already processed
                continue
        return count
