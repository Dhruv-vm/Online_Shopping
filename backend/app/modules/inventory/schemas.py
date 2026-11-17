import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateReservationRequest(BaseModel):
    quote_id: uuid.UUID = Field(
        ..., description="UUID of an active, unexpired checkout quote"
    )
    idempotency_key: str | None = Field(
        None, max_length=128, description="Optional client idempotency key"
    )


class ReservationItemResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class ReservationResponse(BaseModel):
    id: uuid.UUID
    quote_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    status: str
    idempotency_key: str | None = None
    expires_at: datetime
    seconds_remaining: int
    is_expired: bool
    items: list[ReservationItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, reservation: Any) -> "ReservationResponse":
        now = datetime.now(UTC)
        exp = reservation.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        remaining = max(0, int((exp - now).total_seconds()))
        is_exp = reservation.status == "EXPIRED" or remaining <= 0
        return cls(
            id=reservation.id,
            quote_id=reservation.quote_id,
            customer_id=reservation.customer_id,
            status=reservation.status,
            idempotency_key=reservation.idempotency_key,
            expires_at=reservation.expires_at,
            seconds_remaining=remaining,
            is_expired=is_exp,
            items=[
                ReservationItemResponse(
                    id=item.id,
                    listing_id=item.listing_id,
                    retailer_id=item.retailer_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                )
                for item in reservation.items
            ],
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
        )


class ReservationReleaseResponse(BaseModel):
    id: uuid.UUID
    status: str
    released_at: datetime | None
    release_reason: str | None


class ReservationCleanupResponse(BaseModel):
    expired_count: int
    timestamp: datetime
