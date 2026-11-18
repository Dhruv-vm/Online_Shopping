from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ------------------------------------------------------------------------------
# PII Classification & Detection
# ------------------------------------------------------------------------------
# NOTE ON PII DETECTION LIMITATIONS:
# Key-name scanning provides structural defense against accidental inclusion of customer
# PII fields in event data structures. However, scanning key names cannot guarantee that
# arbitrary free-text strings (such as product descriptions, user reviews, support notes,
# or raw error messages) are completely free of personal data. Strict zero-PII compliance
# requires domain aggregate boundaries and payload construction logic to ensure that
# free-text fields are sanitized or omitted before emitting events.
# ------------------------------------------------------------------------------

FORBIDDEN_PII_KEYS = {
    # Direct Customer Identifiers
    "customer_id",
    "guest_token",
    "guest_token_hash",
    "user_id",
    "account_id",
    # Contact Information
    "email",
    "customer_email",
    "user_email",
    "phone",
    "phone_number",
    "customer_phone",
    "mobile",
    "mobile_number",
    "telephone",
    "contact_number",
    # Personal Names
    "full_name",
    "first_name",
    "last_name",
    "customer_name",
    "recipient_name",
    "contact_name",
    # Physical Address Fields
    "address",
    "delivery_address",
    "shipping_address",
    "billing_address",
    "street",
    "street_address",
    "address_line1",
    "address_line2",
    "pincode",
    "pin_code",
    "postal_code",
    "zip_code",
    "zipcode",
    # Financial Credentials & Secrets
    "password",
    "password_hash",
    "card_number",
    "credit_card",
    "debit_card",
    "card_cvv",
    "cvv",
    "cvc",
    "card_expiry",
    "expiry_date",
    "bank_account",
    "account_number",
    "iban",
    # Government Identifiers
    "ssn",
    "pan_number",
    "pan",
    "aadhaar",
    "aadhaar_number",
}

FORBIDDEN_SUBSTRINGS = (
    "customer_id",
    "guest_token",
    "password",
    "card_number",
    "card_cvv",
    "aadhaar",
)


def _check_no_forbidden_keys(data: Any, path: str = "") -> None:
    """Recursively inspect dictionaries and lists to reject customer PII."""
    if isinstance(data, dict):
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            if k_lower in FORBIDDEN_PII_KEYS or any(
                forbidden in k_lower for forbidden in FORBIDDEN_SUBSTRINGS
            ):
                field_path = f"{path}.{k}" if path else str(k)
                raise ValueError(
                    f"Customer PII field '{field_path}' is strictly prohibited in event payloads."
                )
            _check_no_forbidden_keys(v, path=f"{path}.{k}" if path else str(k))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            _check_no_forbidden_keys(item, path=f"{path}[{idx}]")


# ------------------------------------------------------------------------------
# Event-Type-Aware Partition Key Resolver
# ------------------------------------------------------------------------------


def resolve_partition_key(
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
    provided_key: str | None = None,
) -> str:
    """
    Validate and resolve partition key according to Phase 3 aggregate ownership:
    - Orders (order.*): partitioned by order_id
    - Payments (payment.*): partitioned by order_id
    - Catalogue (product.*, listing.*, variant.*, catalogue.*): partitioned by product_id
    - Inventory (inventory.*, store_inventory.*): partitioned by product_id
    - Default: partitioned by aggregate_id
    """
    etype = event_type.lower().strip()
    agg_type = aggregate_type.lower().strip()

    # 1. Orders: order_id
    if etype.startswith("order.") or agg_type == "order":
        if "order_id" in payload:
            expected_id = str(uuid.UUID(str(payload["order_id"])))
        else:
            expected_id = str(aggregate_id)
        if provided_key is not None:
            if str(provided_key).lower() != expected_id.lower():
                raise ValueError(
                    f"partition_key '{provided_key}' for order event must match order_id '{expected_id}'"
                )
            return expected_id
        return expected_id

    # 2. Payments: order_id
    if etype.startswith("payment.") or agg_type in ("payment", "paymentcapture"):
        if "order_id" in payload:
            expected_id = str(uuid.UUID(str(payload["order_id"])))
        elif agg_type == "order":
            expected_id = str(aggregate_id)
        else:
            raise ValueError(
                f"Payment event '{event_type}' must include 'order_id' in payload to determine partition key."
            )
        if provided_key is not None:
            if str(provided_key).lower() != expected_id.lower():
                raise ValueError(
                    f"partition_key '{provided_key}' for payment event must match order_id '{expected_id}'"
                )
            return expected_id
        return expected_id

    # 3. Catalogue: product_id (covers products, listings, variants)
    if etype.startswith(
        ("product.", "catalogue.", "listing.", "variant.")
    ) or agg_type in ("product", "listing", "variant", "catalogue"):
        if "product_id" in payload:
            expected_id = str(uuid.UUID(str(payload["product_id"])))
        elif agg_type == "product":
            expected_id = str(aggregate_id)
        else:
            raise ValueError(
                f"Catalogue/listing event '{event_type}' must include 'product_id' in payload or have Product aggregate."
            )
        if provided_key is not None:
            if str(provided_key).lower() != expected_id.lower():
                raise ValueError(
                    f"partition_key '{provided_key}' for catalogue event must match product_id '{expected_id}'"
                )
            return expected_id
        return expected_id

    # 4. Inventory: product_id
    if etype.startswith(("inventory.", "store_inventory.")) or agg_type in (
        "inventory",
        "storeinventory",
        "store_inventory",
    ):
        if "product_id" in payload:
            expected_id = str(uuid.UUID(str(payload["product_id"])))
        elif agg_type == "product":
            expected_id = str(aggregate_id)
        else:
            raise ValueError(
                f"Inventory event '{event_type}' must include 'product_id' in payload to determine partition key."
            )
        if provided_key is not None:
            if str(provided_key).lower() != expected_id.lower():
                raise ValueError(
                    f"partition_key '{provided_key}' for inventory event must match product_id '{expected_id}'"
                )
            return expected_id
        return expected_id

    # 5. Default Fallback
    expected_id = str(aggregate_id)
    if provided_key is not None:
        if str(provided_key).lower() != expected_id.lower():
            raise ValueError(
                f"partition_key '{provided_key}' must match str(aggregate_id) '{expected_id}'"
            )
        return expected_id
    return expected_id


# ------------------------------------------------------------------------------
# Event Envelope Model
# ------------------------------------------------------------------------------


class EventEnvelope(BaseModel):
    """Canonical domain event envelope schema for BASKET Kafka event streaming."""

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str = Field(..., min_length=3)
    event_version: int = Field(default=1, ge=1)
    aggregate_type: str = Field(..., min_length=1)
    aggregate_id: uuid.UUID
    aggregate_version: int = Field(..., ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    producer: str = Field(default="basket-backend@0.1.0")
    partition_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type", mode="after")
    @classmethod
    def validate_event_type_format(cls, v: str) -> str:
        parts = v.strip().split(".")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"event_type '{v}' must follow '<aggregate>.<action>' notation (e.g. 'order.created')"
            )
        return v.strip()

    @field_validator("occurred_at", mode="after")
    @classmethod
    def ensure_utc_occurred_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("correlation_id", mode="before")
    @classmethod
    def coerce_correlation_id(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v).strip() or None

    @field_validator("payload", mode="after")
    @classmethod
    def validate_payload_pii(cls, v: dict[str, Any]) -> dict[str, Any]:
        _check_no_forbidden_keys(v)
        return v

    @model_validator(mode="after")
    def validate_partition_key(self) -> EventEnvelope:
        self.partition_key = resolve_partition_key(
            event_type=self.event_type,
            aggregate_type=self.aggregate_type,
            aggregate_id=self.aggregate_id,
            payload=self.payload,
            provided_key=self.partition_key,
        )
        return self

    def to_json_dict(self) -> dict[str, Any]:
        """Convert envelope to JSON-serializable dictionary."""
        return json.loads(self.model_dump_json())

    def to_json_bytes(self) -> bytes:
        """Serialize envelope to UTF-8 encoded JSON bytes for Kafka transport."""
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_json_bytes(cls, data: bytes | str) -> EventEnvelope:
        """Parse envelope from JSON bytes or string."""
        if isinstance(data, bytes):
            return cls.model_validate_json(data.decode("utf-8"))
        return cls.model_validate_json(data)
