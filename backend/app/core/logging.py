import logging
import re
import sys

from app.core.config import settings

# user:password@ inside URLs/DSNs, and password=/secret=/token=/key= pairs.
_URL_CREDENTIALS = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.-]*://[^:/@\s]+:)[^@\s]+@")
_KEY_VALUE_SECRETS = re.compile(
    r"(?i)\b((?:[a-z_]*_)?(?:password|passwd|secret|token|api_key|key_secret))"
    r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)


def redact_secrets(text: str) -> str:
    """Mask credentials that may appear in exception text or log arguments."""
    text = _URL_CREDENTIALS.sub(r"\1***@", text)
    return _KEY_VALUE_SECRETS.sub(r"\1\2***", text)


class SanitizeFormatter(logging.Formatter):
    """Formatter that masks credentials before a record is written."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def setup_logging() -> None:
    """Configure root logger for application runtime."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = SanitizeFormatter(
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
