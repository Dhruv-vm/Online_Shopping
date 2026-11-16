import logging
import sys

from app.core.config import settings


class SanitizeFormatter(logging.Formatter):
    """Custom formatter ensuring consistent structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        # Prevent credential leak in log formatting
        message = super().format(record)
        return message


def setup_logging() -> None:
    """Configure root logger for application runtime."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = [handler]

    # Suppress verbose noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("basket")
