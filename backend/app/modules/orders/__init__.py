"""Orders domain module."""

__all__ = [
    "OrderProjectionConsumer",
    "ORDER_PROJECTION_CONSUMER_GROUP",
    "ORDER_PROJECTION_TOPICS",
]


def __getattr__(name: str):
    if name in __all__:
        import app.modules.orders.consumer as _consumer

        return getattr(_consumer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
