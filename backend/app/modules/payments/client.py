import hashlib
import hmac
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.modules.payments.exceptions import (
    PaymentGatewayError,
    PaymentGatewayTimeoutError,
)


class RazorpayClient:
    """Native asynchronous HTTP client for the Razorpay REST API (v1)."""

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.key_id = key_id or (
            settings.RAZORPAY_KEY_ID.get_secret_value()
            if settings.RAZORPAY_KEY_ID
            else ""
        )
        self.key_secret = key_secret or (
            settings.RAZORPAY_KEY_SECRET.get_secret_value()
            if settings.RAZORPAY_KEY_SECRET
            else ""
        )
        self.webhook_secret = webhook_secret or (
            settings.RAZORPAY_WEBHOOK_SECRET.get_secret_value()
            if settings.RAZORPAY_WEBHOOK_SECRET
            else ""
        )
        self.base_url = (base_url or settings.RAZORPAY_BASE_URL).rstrip("/")
        self.timeout = httpx.Timeout(
            connect=settings.RAZORPAY_CONNECT_TIMEOUT_SECONDS,
            read=settings.RAZORPAY_READ_TIMEOUT_SECONDS,
            write=settings.RAZORPAY_READ_TIMEOUT_SECONDS,
            pool=settings.RAZORPAY_CONNECT_TIMEOUT_SECONDS,
        )
        self._transport = transport

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.key_id, self.key_secret),
            timeout=self.timeout,
            transport=self._transport,
            headers={
                "User-Agent": "BASKET-Backend/1.0",
                "Content-Type": "application/json",
            },
        )

    async def create_order(
        self,
        amount_paise: int,
        currency: str = "INR",
        receipt: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create an order with Razorpay: POST /v1/orders."""
        payload: dict[str, Any] = {
            "amount": amount_paise,
            "currency": currency,
            "notes": notes or {},
        }
        if receipt:
            payload["receipt"] = receipt[:40]  # Razorpay receipt max 40 chars

        async with self._get_client() as client:
            try:
                response = await client.post("/orders", json=payload)
            except (
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ) as exc:
                logger.error(
                    "Timeout during Razorpay create_order: %s", type(exc).__name__
                )
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                logger.error("Network error during Razorpay create_order: %s", str(exc))
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code >= 500:
            logger.error(
                "Razorpay 5xx error on create_order: status=%d body=%s",
                response.status_code,
                response.text,
            )
            raise PaymentGatewayError(
                f"Payment gateway returned server error {response.status_code}"
            )
        if response.status_code >= 400:
            logger.error(
                "Razorpay 4xx error on create_order: status=%d body=%s",
                response.status_code,
                response.text,
            )
            data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            err_desc = data.get("error", {}).get(
                "description", "Bad request from payment gateway"
            )
            raise PaymentGatewayError(err_desc, details=data)

        return response.json()

    async def fetch_order(self, order_id: str) -> dict[str, Any]:
        """Fetch order from Razorpay: GET /v1/orders/{order_id}."""
        async with self._get_client() as client:
            try:
                response = await client.get(f"/orders/{order_id}")
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch order: gateway status {response.status_code}"
            )

        return response.json()

    async def fetch_order_payments(
        self, order_id: str, count: int = 10, skip: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch all payments for an order: GET /v1/orders/{order_id}/payments."""
        async with self._get_client() as client:
            try:
                response = await client.get(
                    f"/orders/{order_id}/payments",
                    params={"count": count, "skip": skip},
                )
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch payments for order {order_id}: gateway status {response.status_code}"
            )

        data = response.json()
        return data.get("items", []) if isinstance(data, dict) else []

    async def fetch_orders_by_receipt(
        self, receipt: str, count: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch orders by receipt: GET /v1/orders?receipt={receipt}&count={count}."""
        async with self._get_client() as client:
            try:
                response = await client.get(
                    "/orders", params={"receipt": receipt, "count": count}
                )
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to query orders by receipt: gateway status {response.status_code}"
            )

        data = response.json()
        return data.get("items", [])

    async def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch payment details: GET /v1/payments/{payment_id}."""
        async with self._get_client() as client:
            try:
                response = await client.get(f"/payments/{payment_id}")
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch payment: gateway status {response.status_code}"
            )

        return response.json()

    async def capture_payment(
        self,
        payment_id: str,
        amount_paise: int,
        currency: str = "INR",
    ) -> dict[str, Any]:
        """Server-side capture authorized payment: POST /v1/payments/{payment_id}/capture."""
        payload = {"amount": amount_paise, "currency": currency}
        async with self._get_client() as client:
            try:
                response = await client.post(
                    f"/payments/{payment_id}/capture", json=payload
                )
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError("Capture request timed out") from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError("Network error during capture") from exc

        if response.status_code >= 400:
            data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            err_desc = data.get("error", {}).get(
                "description", f"Capture failed with status {response.status_code}"
            )
            raise PaymentGatewayError(err_desc, details=data)

        return response.json()

    async def create_refund(
        self,
        payment_id: str,
        amount_paise: int,
        idempotency_key: str,
        receipt: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Issue full/partial refund: POST /v1/payments/{payment_id}/refund."""
        payload: dict[str, Any] = {
            "amount": amount_paise,
            "notes": notes or {},
            "receipt": receipt or f"RFND-{idempotency_key[:30]}",
        }
        headers = {"X-Refund-Idempotency": idempotency_key}

        async with self._get_client() as client:
            try:
                response = await client.post(
                    f"/payments/{payment_id}/refund", json=payload, headers=headers
                )
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError("Refund request timed out") from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError("Network error during refund") from exc

        if response.status_code >= 400:
            data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            err_desc = data.get("error", {}).get(
                "description", f"Refund failed with status {response.status_code}"
            )
            raise PaymentGatewayError(err_desc, details=data)

        return response.json()

    async def fetch_refund(self, payment_id: str, refund_id: str) -> dict[str, Any]:
        """Fetch refund details: GET /v1/payments/{payment_id}/refunds/{refund_id}."""
        async with self._get_client() as client:
            try:
                response = await client.get(
                    f"/payments/{payment_id}/refunds/{refund_id}"
                )
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch refund: gateway status {response.status_code}"
            )

        return response.json()

    async def fetch_refund_by_id(self, refund_id: str) -> dict[str, Any]:
        """Fetch refund details directly: GET /v1/refunds/{refund_id}."""
        async with self._get_client() as client:
            try:
                response = await client.get(f"/refunds/{refund_id}")
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch refund: gateway status {response.status_code}"
            )

        return response.json()

    async def fetch_payment_refunds(self, payment_id: str) -> list[dict[str, Any]]:
        """Fetch all refunds for a payment: GET /v1/payments/{payment_id}/refunds."""
        async with self._get_client() as client:
            try:
                response = await client.get(f"/payments/{payment_id}/refunds")
            except httpx.TimeoutException as exc:
                raise PaymentGatewayTimeoutError() from exc
            except httpx.RequestError as exc:
                raise PaymentGatewayError(
                    "Network error contacting payment gateway"
                ) from exc

        if response.status_code != 200:
            raise PaymentGatewayError(
                f"Failed to fetch payment refunds: gateway status {response.status_code}"
            )

        data = response.json()
        return data.get("items", []) if isinstance(data, dict) else []

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verify modal checkout HMAC-SHA256 signature using constant-time comparison."""
        if not self.key_secret:
            logger.error(
                "Cannot verify payment signature: key_secret is not configured"
            )
            return False

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
        expected = hmac.new(
            self.key_secret.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, razorpay_signature)

    def verify_webhook_signature(
        self,
        raw_body_bytes: bytes,
        signature_header: str,
    ) -> bool:
        """Verify webhook HMAC-SHA256 signature using constant-time comparison."""
        if not self.webhook_secret:
            logger.error(
                "Cannot verify webhook signature: webhook_secret is not configured"
            )
            return False

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), raw_body_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
