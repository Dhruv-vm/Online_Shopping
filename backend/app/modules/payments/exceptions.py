from typing import Any

from fastapi import status

from app.core.exceptions import AppException


class PaymentGatewayError(AppException):
    def __init__(
        self,
        message: str = "Payment gateway unavailable",
        details: list[Any] | None = None,
    ):
        super().__init__(
            code="GATEWAY_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class PaymentGatewayTimeoutError(AppException):
    def __init__(
        self,
        message: str = "Payment creation request timed out and requires reconciliation",
    ):
        super().__init__(
            code="PAYMENT_CREATION_AMBIGUOUS",
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class PaymentNotFoundError(AppException):
    def __init__(self, message: str = "Payment not found"):
        super().__init__(
            code="PAYMENT_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class PaymentAlreadyConfirmedError(AppException):
    def __init__(self, message: str = "Order is already confirmed"):
        super().__init__(
            code="ORDER_ALREADY_CONFIRMED",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class PaymentAttemptAmbiguousError(AppException):
    def __init__(
        self,
        message: str = "Active payment attempt is ambiguous and requires reconciliation before retry",
    ):
        super().__init__(
            code="PAYMENT_ATTEMPT_AMBIGUOUS",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class PaymentWindowExpiredError(AppException):
    def __init__(self, message: str = "Checkout payment window has expired"):
        super().__init__(
            code="PAYMENT_WINDOW_EXPIRED",
            message=message,
            status_code=status.HTTP_410_GONE,
        )


class InvalidPaymentSignatureError(AppException):
    def __init__(self, message: str = "Invalid payment signature"):
        super().__init__(
            code="SIGNATURE_VERIFICATION_FAILED",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class PartialCaptureRejectedError(AppException):
    def __init__(
        self,
        message: str = "Partial capture is not supported; payment rejected and queued for refund",
    ):
        super().__init__(
            code="PARTIAL_CAPTURE_REJECTED",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ExceedsRefundableBalanceError(AppException):
    def __init__(
        self,
        message: str = "Refund amount exceeds remaining refundable capture balance",
    ):
        super().__init__(
            code="REFUND_EXCEEDS_CAPTURED_AMOUNT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidWebhookSignatureError(AppException):
    def __init__(self, message: str = "Invalid webhook signature"):
        super().__init__(
            code="WEBHOOK_SIGNATURE_INVALID",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MissingWebhookSignatureError(AppException):
    def __init__(self, message: str = "Missing x-razorpay-signature header"):
        super().__init__(
            code="WEBHOOK_SIGNATURE_MISSING",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
