import hmac
from typing import Annotated

from fastapi import Header, status

from app.core.config import settings
from app.core.exceptions import AppException


async def verify_internal_service_key(
    x_internal_service_key: Annotated[
        str | None, Header(alias="X-Internal-Service-Key")
    ] = None,
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """Verifies that the request carries a valid internal service key or token.

    Rejects unauthenticated callers, customers, and guests attempting to access internal routes.
    """
    token = x_internal_service_key or x_internal_token
    if not token or not settings.INTERNAL_SERVICE_KEY:
        raise AppException(
            code="UNAUTHORIZED",
            message="Internal service authorization required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    configured_key = settings.INTERNAL_SERVICE_KEY.get_secret_value()
    if not configured_key or not hmac.compare_digest(token, configured_key):
        raise AppException(
            code="UNAUTHORIZED",
            message="Invalid or missing internal service authorization.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
