"""Admin audit-trail middleware."""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import Request, Response

logger = logging.getLogger(__name__)

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


async def record_admin_mutation(request: Request, response: Response) -> None:
    """Persist one audit row for a successful mutation performed by an admin."""
    if request.method not in _MUTATING or response.status_code >= 400:
        return
    if getattr(request.state, "auth_role", None) != "admin":
        return
    try:
        from app.core.database import get_session_factory
        from app.modules.governance.models import AdminAuditLog

        factory = get_session_factory()
        if factory is None:
            return
        route = request.scope.get("route")
        template = getattr(route, "path", None) or request.url.path
        match = _UUID_RE.search(request.url.path)
        async with factory() as session:
            session.add(
                AdminAuditLog(
                    id=uuid.uuid4(),
                    actor_user_id=getattr(request.state, "auth_user_id", None),
                    actor_email=getattr(request.state, "auth_user_email", None),
                    method=request.method,
                    route=str(template)[:255],
                    path=request.url.path[:512],
                    entity_id=match.group(0) if match else None,
                    status_code=response.status_code,
                    request_id=getattr(request.state, "request_id", None),
                    ip_address=(request.client.host if request.client else None),
                    details={"query": str(request.url.query)[:500]}
                    if request.url.query
                    else {},
                )
            )
            await session.commit()
    except Exception as exc:  # audit failures must never break the request
        logger.error("Failed to write admin audit log: %s", type(exc).__name__)
