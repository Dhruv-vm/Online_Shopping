import abc
import enum
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import CustomerNotification

logger = logging.getLogger(__name__)


class NotificationChannel(enum.StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    IN_APP = "IN_APP"


class NotificationEventType(enum.StrEnum):
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_PROCESSING = "ORDER_PROCESSING"
    ORDER_PACKED = "ORDER_PACKED"
    ORDER_SHIPPED = "ORDER_SHIPPED"
    ORDER_OUT_FOR_DELIVERY = "ORDER_OUT_FOR_DELIVERY"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURN_APPROVED = "RETURN_APPROVED"
    RETURN_REJECTED = "RETURN_REJECTED"
    RETURN_REFUNDED = "RETURN_REFUNDED"


class BaseMessageProvider(abc.ABC):
    @abc.abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send message via the provider."""
        ...


class LoggingEmailProvider(BaseMessageProvider):
    """Clean logging email provider.

    Does not fabricate fake SMTP or third-party delivery responses.
    """

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info(
            "DISPATCH EMAIL [event=%s, to=%s, subject=%s]",
            event_type,
            recipient,
            subject,
        )
        return True


class LoggingSmsProvider(BaseMessageProvider):
    """Clean logging SMS provider.

    Does not fabricate fake external SMS gateway responses.
    """

    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        logger.info(
            "DISPATCH SMS [event=%s, to=%s, message=%s]",
            event_type,
            recipient,
            body,
        )
        return True


class InAppNotificationDispatcher:
    """Dispatches durable in-app notifications stored in PostgreSQL."""

    @staticmethod
    async def dispatch(
        session: AsyncSession,
        title: str,
        message: str,
        event_type: str,
        customer_id: uuid.UUID | None = None,
        guest_token_hash: str | None = None,
        order_id: uuid.UUID | None = None,
    ) -> CustomerNotification:
        notification = CustomerNotification(
            customer_id=customer_id,
            guest_token_hash=guest_token_hash,
            order_id=order_id,
            title=title,
            message=message,
            event_type=event_type,
            is_read=False,
        )
        session.add(notification)
        return notification


email_provider: BaseMessageProvider = LoggingEmailProvider()
sms_provider: BaseMessageProvider = LoggingSmsProvider()


def get_email_provider() -> BaseMessageProvider:
    return email_provider


def get_sms_provider() -> BaseMessageProvider:
    return sms_provider
