"""Orders domain module."""

from app.modules.orders.consumer import (
    ORDER_PROJECTION_CONSUMER_GROUP,
    ORDER_PROJECTION_TOPICS,
    OrderProjectionConsumer,
)

__all__ = [
    "OrderProjectionConsumer",
    "ORDER_PROJECTION_CONSUMER_GROUP",
    "ORDER_PROJECTION_TOPICS",
]
