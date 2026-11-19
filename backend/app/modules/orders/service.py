import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.inventory.models import ReservationStatus
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
)
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import CreateOrderRequest
from app.modules.pricing.models import QuoteStatus

logger = logging.getLogger(__name__)


def compute_canonical_request_hash(
    req: CreateOrderRequest | None = None,
    customer_id: uuid.UUID | None = None,
    guest_token_hash: str | None = None,
    address_snapshot: dict[str, Any] | None = None,
    *,
    quote_id: uuid.UUID | None = None,
    reservation_id: uuid.UUID | None = None,
) -> str:
    """Computes a deterministic SHA-256 fingerprint over all meaningful checkout inputs."""
    eff_quote_id = quote_id or (req.quote_id if req else None)
    eff_res_id = reservation_id or (req.reservation_id if req else None)

    data: dict[str, Any] = {
        "quote_id": str(eff_quote_id),
        "reservation_id": str(eff_res_id),
    }

    if address_snapshot:
        data["delivery_address"] = {
            "full_name": address_snapshot.get("full_name", "").strip(),
            "address_line1": address_snapshot.get("address_line1", "").strip(),
            "address_line2": (address_snapshot.get("address_line2") or "").strip(),
            "city": address_snapshot.get("city", "").strip(),
            "state": address_snapshot.get("state", "").strip(),
            "postal_code": address_snapshot.get("postal_code", "").strip(),
            "phone": address_snapshot.get("phone", "").strip(),
        }
    elif req and req.delivery_address_id:
        data["delivery_address"] = {
            "type": "saved",
            "address_id": str(req.delivery_address_id),
        }
    elif req and req.delivery_address:
        data["delivery_address"] = {
            "type": "inline",
            "full_name": req.delivery_address.full_name.strip(),
            "address_line1": req.delivery_address.address_line1.strip(),
            "address_line2": (req.delivery_address.address_line2 or "").strip(),
            "city": req.delivery_address.city.strip(),
            "state": req.delivery_address.state.strip(),
            "postal_code": req.delivery_address.postal_code.strip(),
            "phone": req.delivery_address.phone.strip(),
        }

    if customer_id:
        data["caller"] = {"customer_id": str(customer_id)}
    elif guest_token_hash:
        data["caller"] = {"guest_token_hash": guest_token_hash}

    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OrderRepository(session)

    async def create_order(
        self,
        req: CreateOrderRequest,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> Order:
        """Atomic PostgreSQL transaction creating an order from active quote and reservation."""
        if not customer_id and not guest_token_hash:
            raise AppException(
                code="UNAUTHORIZED",
                message="Authentication or guest session is required.",
                status_code=401,
            )

        now = datetime.now(UTC)

        # 1. Derive effective quote_id and peek reservation if quote_id was omitted
        effective_quote_id = req.quote_id
        if not effective_quote_id:
            res_peek = await self.repo.get_reservation_by_id(req.reservation_id)
            if not res_peek:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Inventory reservation was not found.",
                    status_code=404,
                )
            effective_quote_id = res_peek.quote_id

        # 2. Resolve Delivery Address snapshot early to compute canonical request hash
        address_snapshot: dict[str, Any]
        if req.delivery_address_id:
            if not customer_id:
                raise AppException(
                    code="INVALID_ADDRESS_SELECTION",
                    message="Saved addresses are only accessible to authenticated customers.",
                    status_code=400,
                )
            saved_addr = await self.repo.get_customer_address(
                req.delivery_address_id, customer_id
            )
            if not saved_addr:
                raise AppException(
                    code="ADDRESS_NOT_FOUND",
                    message="Selected delivery address was not found.",
                    status_code=404,
                )
            address_snapshot = {
                "full_name": saved_addr.recipient_name,
                "address_line1": saved_addr.line1,
                "address_line2": saved_addr.line2,
                "city": saved_addr.city,
                "state": saved_addr.state,
                "postal_code": saved_addr.postal_code,
                "phone": saved_addr.phone,
            }
        elif req.delivery_address:
            address_snapshot = {
                "full_name": req.delivery_address.full_name,
                "address_line1": req.delivery_address.address_line1,
                "address_line2": req.delivery_address.address_line2,
                "city": req.delivery_address.city,
                "state": req.delivery_address.state,
                "postal_code": req.delivery_address.postal_code,
                "phone": req.delivery_address.phone,
            }
        elif customer_id:
            # Authenticated customer without explicit delivery_address_id: use saved default address
            saved_default = await self.repo.get_default_customer_address(customer_id)
            if saved_default:
                address_snapshot = {
                    "full_name": saved_default.recipient_name,
                    "address_line1": saved_default.line1,
                    "address_line2": saved_default.line2,
                    "city": saved_default.city,
                    "state": saved_default.state,
                    "postal_code": saved_default.postal_code,
                    "phone": saved_default.phone,
                }
            else:
                address_snapshot = {
                    "full_name": "Valued Customer",
                    "address_line1": "Standard Delivery",
                    "address_line2": None,
                    "city": "Bengaluru",
                    "state": "KA",
                    "postal_code": "560001",
                    "phone": "+919876543210",
                }
        else:
            # Guest checkout without delivery address ID: default guest delivery address
            address_snapshot = {
                "full_name": "Guest Customer",
                "address_line1": "Standard Delivery",
                "address_line2": None,
                "city": "Bengaluru",
                "state": "KA",
                "postal_code": "560001",
                "phone": "+919876543210",
            }

        # 3. Check Idempotency Record (Fast return before locking resources)
        req_hash = compute_canonical_request_hash(
            req=req,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            address_snapshot=address_snapshot,
            quote_id=effective_quote_id,
            reservation_id=req.reservation_id,
        )

        if req.idempotency_key:
            existing_record = await self.repo.get_idempotency_record(
                scope="order_placement",
                customer_id=customer_id,
                guest_token_hash=guest_token_hash,
                idempotency_key=req.idempotency_key,
            )
            if existing_record:
                if existing_record.request_hash == req_hash:
                    cached_order = await self.repo.get_order_by_id(
                        existing_record.order_id
                    )
                    if cached_order:
                        return cached_order
                else:
                    raise AppException(
                        code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                        message="This idempotency key was previously used with a different request payload.",
                        status_code=409,
                    )

        # 4. Lock & Validate Checkout Quote
        quote = await self.repo.lock_quote_for_update(effective_quote_id)
        if not quote:
            raise AppException(
                code="QUOTE_NOT_FOUND",
                message="Checkout quote was not found.",
                status_code=404,
            )

        # Check idempotency record again after lock acquisition in case concurrent request completed while waiting
        if req.idempotency_key:
            existing_record = await self.repo.get_idempotency_record(
                scope="order_placement",
                customer_id=customer_id,
                guest_token_hash=guest_token_hash,
                idempotency_key=req.idempotency_key,
            )
            if existing_record:
                if existing_record.request_hash == req_hash:
                    cached_order = await self.repo.get_order_by_id(
                        existing_record.order_id
                    )
                    if cached_order:
                        return cached_order
                else:
                    raise AppException(
                        code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                        message="This idempotency key was previously used with a different request payload.",
                        status_code=409,
                    )

        # Ownership validation
        if customer_id:
            if quote.customer_id != customer_id:
                raise AppException(
                    code="QUOTE_NOT_FOUND",
                    message="Checkout quote was not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if (
                quote.guest_token_hash != guest_token_hash
                or quote.customer_id is not None
            ):
                raise AppException(
                    code="QUOTE_NOT_FOUND",
                    message="Checkout quote was not found.",
                    status_code=404,
                )

        if quote.is_consumed:
            raise AppException(
                code="QUOTE_ALREADY_CONSUMED",
                message="This quote has already been ordered and consumed.",
                status_code=409,
            )

        q_exp = (
            quote.expires_at.replace(tzinfo=UTC)
            if quote.expires_at.tzinfo is None
            else quote.expires_at
        )
        if q_exp < now:
            raise AppException(
                code="QUOTE_EXPIRED",
                message="Checkout quote has expired. Please refresh your quote.",
                status_code=409,
            )

        if quote.status != QuoteStatus.ACTIVE.value:
            raise AppException(
                code="QUOTE_INVALID_STATUS",
                message=f"Quote status is {quote.status}. Only active quotes can be ordered.",
                status_code=409,
            )

        # 5. Lock & Validate Inventory Reservation
        res = await self.repo.lock_reservation_for_update(req.reservation_id)
        if not res:
            raise AppException(
                code="RESERVATION_NOT_FOUND",
                message="Inventory reservation was not found.",
                status_code=404,
            )

        if res.quote_id != quote.id:
            raise AppException(
                code="RESERVATION_QUOTE_MISMATCH",
                message="Reservation does not belong to the specified quote.",
                status_code=400,
            )

        # Reservation ownership validation
        if customer_id:
            if res.customer_id != customer_id:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Inventory reservation was not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if res.guest_token_hash != guest_token_hash or res.customer_id is not None:
                raise AppException(
                    code="RESERVATION_NOT_FOUND",
                    message="Inventory reservation was not found.",
                    status_code=404,
                )

        if res.status == ReservationStatus.CONFIRMED.value:
            raise AppException(
                code="RESERVATION_ALREADY_CONFIRMED",
                message="Reservation is already confirmed.",
                status_code=409,
            )
        if res.status == ReservationStatus.EXPIRED.value:
            raise AppException(
                code="RESERVATION_EXPIRED",
                message="Reservation hold has expired.",
                status_code=409,
            )
        if res.status == ReservationStatus.RELEASED.value:
            raise AppException(
                code="RESERVATION_RELEASED",
                message="Reservation hold has been released.",
                status_code=409,
            )

        res_exp = (
            res.expires_at.replace(tzinfo=UTC)
            if res.expires_at.tzinfo is None
            else res.expires_at
        )
        if res_exp < now:
            raise AppException(
                code="RESERVATION_EXPIRED",
                message="Reservation hold has expired.",
                status_code=409,
            )

        # 5. Generate Human-Readable Order Number
        today_str = now.strftime("%Y%m%d")
        rand_suffix = uuid.uuid4().hex[:8].upper()
        order_number = f"BSK-{today_str}-{rand_suffix}"

        order_id = uuid.uuid4()
        payment_window_expires_at = min(res_exp, now + timedelta(minutes=15))

        # 6. Create Order and OrderItems
        order = Order(
            id=order_id,
            order_number=order_number,
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            quote_id=quote.id,
            reservation_id=res.id,
            delivery_address_snapshot=address_snapshot,
            subtotal_paise=quote.subtotal_paise,
            discount_total_paise=quote.discount_total_paise,
            delivery_fee_paise=quote.delivery_fee_paise,
            cgst_paise=quote.cgst_paise,
            sgst_paise=quote.sgst_paise,
            igst_paise=quote.igst_paise,
            total_tax_paise=quote.total_tax_paise,
            total_payable_paise=quote.total_payable_paise,
            currency=quote.currency,
            status=OrderStatus.PENDING_PAYMENT.value,
            payment_status=PaymentStatus.NOT_INITIATED.value,
            version=1,
            idempotency_key=req.idempotency_key,
            payment_window_expires_at=payment_window_expires_at,
            items=[
                OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    listing_id=item.listing_id,
                    variant_id=item.variant_id,
                    retailer_id=item.retailer_id,
                    product_title=item.product_title,
                    variant_title=item.variant_title,
                    sku=item.sku,
                    hsn_code=item.hsn_code,
                    gst_rate_basis_points=item.gst_rate_basis_points,
                    quantity=item.quantity,
                    unit_original_price_paise=item.unit_original_price_paise,
                    unit_selling_price_paise=item.unit_selling_price_paise,
                    unit_discount_paise=item.unit_discount_paise,
                    unit_discounted_price_paise=item.unit_discounted_price_paise,
                    total_selling_price_paise=item.total_selling_price_paise,
                    taxable_base_paise=item.taxable_base_paise,
                    cgst_paise=item.cgst_paise,
                    sgst_paise=item.sgst_paise,
                    igst_paise=item.igst_paise,
                    total_tax_paise=item.total_tax_paise,
                    retailer_name=item.retailer_name,
                    retailer_state=item.retailer_state,
                )
                for item in quote.items
            ],
            status_history=[
                OrderStatusHistory(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    from_status=None,
                    to_status=OrderStatus.PENDING_PAYMENT.value,
                    reason="ORDER_CREATED",
                )
            ],
        )
        self.repo.add_order(order)
        # Flush order first so its primary key exists before linking in inventory_reservations
        await self.repo.flush()

        # 7. Allocate Reservation to Order (Protects hold from ordinary cleanup)
        res.status = ReservationStatus.ALLOCATED_TO_ORDER.value
        res.order_id = order_id

        # 8. Consume Quote
        quote.is_consumed = True
        quote.status = QuoteStatus.CONSUMED.value
        quote.consumed_at = now

        # 9. Selective Cart Reconciliation
        if quote.cart_id:
            cart_items = await self.repo.get_cart_items_for_update(quote.cart_id)
            current_by_listing = {c_item.listing_id: c_item for c_item in cart_items}
            for q_item in quote.items:
                c_item = current_by_listing.get(q_item.listing_id)
                if not c_item:
                    continue
                if c_item.quantity <= q_item.quantity:
                    await self.session.delete(c_item)
                else:
                    c_item.quantity -= q_item.quantity

        # 10. Record Zero-PII Outbox Event
        outbox_payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "order.created",
            "schema_version": 1,
            "aggregate_id": str(order_id),
            "order_number": order_number,
            "customer_id": str(customer_id) if customer_id else None,
            "is_guest": customer_id is None,
            "quote_id": str(quote.id),
            "reservation_id": str(res.id),
            "currency": quote.currency,
            "subtotal_paise": quote.subtotal_paise,
            "discount_total_paise": quote.discount_total_paise,
            "delivery_fee_paise": quote.delivery_fee_paise,
            "cgst_paise": quote.cgst_paise,
            "sgst_paise": quote.sgst_paise,
            "igst_paise": quote.igst_paise,
            "total_tax_paise": quote.total_tax_paise,
            "total_payable_paise": quote.total_payable_paise,
            "status": OrderStatus.PENDING_PAYMENT.value,
            "payment_status": PaymentStatus.NOT_INITIATED.value,
            "items": [
                {
                    "listing_id": str(item.listing_id),
                    "retailer_id": str(item.retailer_id),
                    "variant_id": str(item.variant_id),
                    "quantity": item.quantity,
                    "unit_selling_price_paise": item.unit_selling_price_paise,
                    "total_selling_price_paise": item.total_selling_price_paise,
                    "total_tax_paise": item.total_tax_paise,
                    "hsn_code": item.hsn_code,
                    "gst_rate_basis_points": item.gst_rate_basis_points,
                }
                for item in quote.items
            ],
            "created_at": now.isoformat(),
            "aggregate_version": order.version,
        }
        await self.repo.create_outbox_event(
            aggregate_type="order",
            aggregate_id=order_id,
            event_type="order.created",
            schema_version=1,
            payload=outbox_payload,
            aggregate_version=order.version,
        )

        # 11. Record Idempotency
        if req.idempotency_key:
            await self.repo.create_idempotency_record(
                scope="order_placement",
                customer_id=customer_id,
                guest_token_hash=guest_token_hash,
                idempotency_key=req.idempotency_key,
                request_hash=req_hash,
                order_id=order_id,
                expires_at=now + timedelta(days=1),
            )

        # 12. Flush and Concurrency Error Handling
        quote_id_val = quote.id
        try:
            await self.repo.flush()
        except IntegrityError as exc:
            import logging

            logging.getLogger("basket").error("ORDER FLUSH INTEGRITY ERROR: %s", exc)
            await self.session.rollback()
            # Handle concurrent race:
            # Check if this quote was already ordered by a winning transaction
            existing_order = await self.repo.get_order_by_quote_id(quote_id_val)
            if existing_order:
                if req.idempotency_key:
                    existing_record = await self.repo.get_idempotency_record(
                        scope="order_placement",
                        customer_id=customer_id,
                        guest_token_hash=guest_token_hash,
                        idempotency_key=req.idempotency_key,
                    )
                    if (
                        existing_record
                        and existing_record.request_hash == req_hash
                        and existing_record.order_id == existing_order.id
                    ):
                        return existing_order
                raise AppException(
                    code="QUOTE_ALREADY_ORDERED",
                    message="An order for this quote has already been created.",
                    status_code=409,
                ) from None
            raise AppException(
                code="ORDER_CREATION_CONFLICT",
                message="A conflicting order is currently being processed. Please retry.",
                status_code=409,
            ) from None

        return order

    async def get_order(
        self,
        order_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> Order:
        """Fetches order by ID enforcing strict tenant isolation and anti-IDOR protection."""
        order = await self.repo.get_order_by_id(order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order was not found.",
                status_code=404,
            )

        if customer_id:
            if order.customer_id != customer_id:
                raise AppException(
                    code="ORDER_NOT_FOUND",
                    message="Order was not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if (
                order.guest_token_hash != guest_token_hash
                or order.customer_id is not None
            ):
                raise AppException(
                    code="ORDER_NOT_FOUND",
                    message="Order was not found.",
                    status_code=404,
                )
        else:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order was not found.",
                status_code=404,
            )

        return order

    async def list_orders(
        self,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lists orders belonging to authenticated customer or authorized guest."""
        if not customer_id and not guest_token_hash:
            raise AppException(
                code="UNAUTHORIZED",
                message="Authentication or guest session is required.",
                status_code=401,
            )

        orders, total = await self.repo.list_orders(
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            skip=skip,
            limit=limit,
        )

        items = [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "payment_status": o.payment_status,
                "total_payable_paise": o.total_payable_paise,
                "currency": o.currency,
                "item_count": sum(item.quantity for item in o.items),
                "created_at": o.created_at,
            }
            for o in orders
        ]
        return items, total

    async def cancel_order(
        self,
        order_id: uuid.UUID,
        reason: str = "CUSTOMER_CANCELLED",
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
    ) -> Order:
        """Transactionally cancels an order with strictly monotonic aggregate versioning and idempotency.

        Invariants:
        1. Exclusively locks the order row with SELECT ... FOR UPDATE.
        2. Validates tenant ownership (customer or guest).
        3. If already CANCELLED: returns order idempotently without allocating new version or outbox event.
        4. Validates valid transition state (PENDING_PAYMENT or CONFIRMED).
        5. Atomically increments order.version (monotonic aggregate version).
        6. Persists OrderStatusHistory and OutboxEvent transactionally in the same DB transaction.
        7. If reservation hold is active, safely releases it.
        """
        order = await self.repo.get_order_by_id_for_update(order_id)
        if not order:
            raise AppException(
                code="ORDER_NOT_FOUND",
                message="Order was not found.",
                status_code=404,
            )

        if customer_id:
            if order.customer_id != customer_id:
                raise AppException(
                    code="ORDER_NOT_FOUND",
                    message="Order was not found.",
                    status_code=404,
                )
        elif guest_token_hash:
            if (
                order.guest_token_hash != guest_token_hash
                or order.customer_id is not None
            ):
                raise AppException(
                    code="ORDER_NOT_FOUND",
                    message="Order was not found.",
                    status_code=404,
                )

        # Idempotent check: repeated cancellations are no-ops with zero new version/outbox allocation
        if order.status == OrderStatus.CANCELLED.value:
            return order

        # Transition validation
        if order.status not in (
            OrderStatus.PENDING_PAYMENT.value,
            OrderStatus.CONFIRMED.value,
        ):
            raise AppException(
                code="INVALID_ORDER_STATE",
                message=f"Order in status {order.status} cannot be cancelled.",
                status_code=400,
            )

        from_status = order.status
        order.version += 1
        order.status = OrderStatus.CANCELLED.value
        if from_status == OrderStatus.PENDING_PAYMENT.value:
            order.payment_status = PaymentStatus.FAILED.value

        history = OrderStatusHistory(
            order_id=order.id,
            from_status=from_status,
            to_status=OrderStatus.CANCELLED.value,
            reason=reason,
        )
        self.session.add(history)

        outbox_payload = {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "cancel_reason": reason,
            "aggregate_version": order.version,
        }
        await self.repo.create_outbox_event(
            aggregate_type="order",
            aggregate_id=order.id,
            event_type="order.cancelled",
            schema_version=1,
            payload=outbox_payload,
            aggregate_version=order.version,
        )

        # Release reservation hold if order was unpaid
        if from_status == OrderStatus.PENDING_PAYMENT.value and order.reservation_id:
            try:
                from app.modules.inventory.service import ReservationService

                res_service = ReservationService(self.session)
                await res_service.release_reservation(
                    reservation_id=order.reservation_id,
                    reason=reason,
                    internal=True,
                )
            except Exception as e:
                logger.warning(
                    "Failed to release reservation on cancel for order %s: %s",
                    order.id,
                    e,
                )

        await self.session.flush()
        return order
