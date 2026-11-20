"""Admin governance: user management, order visibility, audit logs and
operational health."""

from __future__ import annotations

import datetime
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import AppException
from app.modules.governance.models import AdminAuditLog
from app.modules.identity.dependencies import require_admin, verify_csrf_token
from app.modules.identity.models import User, UserSession
from app.modules.orders.models import Order, OrderItem, OutboxEvent

router = APIRouter(
    prefix="/admin",
    tags=["Admin Governance"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


# ------------------------------------------------------------------ users
class AdminUserItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    preferred_language: str | None
    is_test_fixture: bool
    created_at: datetime.datetime


class AdminUserList(BaseModel):
    items: list[AdminUserItem]
    total: int


class UserStatusRequest(BaseModel):
    is_active: bool
    reason: str = Field(..., min_length=3, max_length=300)


def _quarantined_users():
    from app.modules.data_quality.models import DataQuarantine

    return select(DataQuarantine.entity_id).where(
        DataQuarantine.entity_type == "user", DataQuarantine.restored_at.is_(None)
    )


@router.get("/users", response_model=AdminUserList)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    role: Literal["customer", "retailer", "admin"] | None = None,
    is_active: bool | None = None,
    include_test_fixtures: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserList:
    conds = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        conds.append(or_(User.email.ilike(term), User.full_name.ilike(term)))
    if role:
        conds.append(User.role == role)
    if is_active is not None:
        conds.append(User.is_active.is_(is_active))
    quarantined = _quarantined_users()
    if not include_test_fixtures:
        conds.append(~User.id.in_(quarantined))
    total = (
        await db.execute(select(func.count()).select_from(User).where(*conds))
    ).scalar() or 0
    rows = (
        await db.execute(
            select(User, User.id.in_(quarantined).label("is_fixture"))
            .where(*conds)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return AdminUserList(
        items=[
            AdminUserItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                is_active=u.is_active,
                preferred_language=getattr(u, "preferred_language", None),
                is_test_fixture=bool(fx),
                created_at=u.created_at,
            )
            for u, fx in rows
        ],
        total=total,
    )


@router.post("/users/{user_id}/status", response_model=AdminUserItem)
async def set_user_status(
    user_id: uuid.UUID,
    payload: UserStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> AdminUserItem:
    """Suspend or reinstate an account. Suspension revokes all sessions."""
    if user_id == admin.id:
        raise AppException(
            code="CANNOT_MODIFY_SELF",
            message="You cannot change the status of your own account.",
            status_code=409,
        )
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND", message="User not found.", status_code=404
        )
    user.is_active = payload.is_active
    if not payload.is_active:
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.is_revoked.is_(False))
            .values(is_revoked=True)
        )
    await db.flush()
    return AdminUserItem(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        preferred_language=getattr(user, "preferred_language", None),
        is_test_fixture=False,
        created_at=user.created_at,
    )


# ------------------------------------------------------------------ orders
class AdminOrderItem(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_email: str | None
    status: str
    payment_status: str
    total_payable_paise: int
    item_count: int
    retailer_count: int
    created_at: datetime.datetime


class AdminOrderList(BaseModel):
    items: list[AdminOrderItem]
    total: int


@router.get("/orders", response_model=AdminOrderList)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
    payment_status: str | None = None,
    q: str | None = Query(None, description="Order number or customer email"),
    include_test_fixtures: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminOrderList:
    conds = []
    if status:
        conds.append(Order.status == status.upper())
    if payment_status:
        conds.append(Order.payment_status == payment_status.upper())
    if q and q.strip():
        term = f"%{q.strip()}%"
        conds.append(or_(Order.order_number.ilike(term), User.email.ilike(term)))
    if not include_test_fixtures:
        conds.append(
            or_(
                Order.customer_id.is_(None),
                ~Order.customer_id.in_(_quarantined_users()),
            )
        )
    base = select(Order).outerjoin(User, User.id == Order.customer_id).where(*conds)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    counts = (
        select(
            OrderItem.order_id,
            func.sum(OrderItem.quantity).label("qty"),
            func.count(func.distinct(OrderItem.retailer_id)).label("rets"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Order, User.email, counts.c.qty, counts.c.rets)
            .outerjoin(User, User.id == Order.customer_id)
            .outerjoin(counts, counts.c.order_id == Order.id)
            .where(*conds)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return AdminOrderList(
        items=[
            AdminOrderItem(
                id=o.id,
                order_number=o.order_number,
                customer_email=email,
                status=o.status,
                payment_status=o.payment_status,
                total_payable_paise=int(o.total_payable_paise),
                item_count=int(qty or 0),
                retailer_count=int(rets or 0),
                created_at=o.created_at,
            )
            for o, email, qty, rets in rows
        ],
        total=total,
    )


# ------------------------------------------------------------------ audit
class AuditItem(BaseModel):
    id: uuid.UUID
    actor_email: str | None
    method: str
    route: str
    path: str
    entity_id: str | None
    status_code: int
    created_at: datetime.datetime


class AuditList(BaseModel):
    items: list[AuditItem]
    total: int


@router.get("/audit-logs", response_model=AuditList)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: str | None = Query(None, description="Actor email contains"),
    entity_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditList:
    conds = []
    if actor:
        conds.append(AdminAuditLog.actor_email.ilike(f"%{actor.strip()}%"))
    if entity_id:
        conds.append(AdminAuditLog.entity_id == entity_id.strip())
    total = (
        await db.execute(select(func.count()).select_from(AdminAuditLog).where(*conds))
    ).scalar() or 0
    rows = (
        await db.execute(
            select(AdminAuditLog)
            .where(*conds)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return AuditList(
        items=[
            AuditItem(
                id=r.id,
                actor_email=r.actor_email,
                method=r.method,
                route=r.route,
                path=r.path,
                entity_id=r.entity_id,
                status_code=r.status_code,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
    )


# ------------------------------------------------------------------ health
class ComponentHealth(BaseModel):
    name: str
    status: Literal["ok", "degraded", "down", "not_configured"]
    detail: str


class SystemHealth(BaseModel):
    components: list[ComponentHealth]
    outbox_pending: int
    outbox_failed: int
    oldest_pending_event_seconds: int | None
    background_jobs: dict
    quarantined_test_records: int
    checked_at: datetime.datetime


@router.get("/system/health", response_model=SystemHealth)
async def system_health(db: Annotated[AsyncSession, Depends(get_db)]) -> SystemHealth:
    from app.core.background import JOB_STATUS
    from app.modules.data_quality.models import DataQuarantine

    comps: list[ComponentHealth] = []
    try:
        await db.execute(text("SELECT 1"))
        comps.append(
            ComponentHealth(name="PostgreSQL", status="ok", detail="Reachable")
        )
    except Exception as exc:  # pragma: no cover
        comps.append(
            ComponentHealth(name="PostgreSQL", status="down", detail=type(exc).__name__)
        )

    pending, failed, oldest = (
        await db.execute(
            select(
                func.count().filter(OutboxEvent.status.in_(("PENDING", "PROCESSING"))),
                func.count().filter(OutboxEvent.status == "FAILED"),
                func.min(OutboxEvent.created_at).filter(
                    OutboxEvent.status == "PENDING"
                ),
            )
        )
    ).one()
    now = datetime.datetime.now(datetime.UTC)
    oldest_s = int((now - oldest).total_seconds()) if oldest else None

    kafka = (settings.KAFKA_BOOTSTRAP_SERVERS or "").strip()
    if not kafka:
        comps.append(
            ComponentHealth(
                name="Kafka",
                status="not_configured",
                detail="Events stay in the outbox",
            )
        )
    else:
        comps.append(
            ComponentHealth(
                name="Kafka",
                status="degraded" if (oldest_s or 0) > 300 else "ok",
                detail=f"{pending} event(s) awaiting publish",
            )
        )
    os_url = (getattr(settings, "OPENSEARCH_URL", "") or "").strip()
    comps.append(
        ComponentHealth(
            name="OpenSearch",
            status="ok" if os_url else "not_configured",
            detail="Configured" if os_url else "Search uses PostgreSQL",
        )
    )
    rzp_secret = getattr(settings, "RAZORPAY_KEY_ID", None)
    rzp = rzp_secret.get_secret_value() if rzp_secret else ""
    if not rzp or "mock" in rzp:
        rzp_status, rzp_detail = (
            "not_configured",
            "No real Razorpay keys (mock key only)",
        )
    else:
        rzp_status = "ok"
        rzp_detail = (
            "Test-mode keys configured"
            if rzp.startswith("rzp_test_")
            else "Live keys configured"
        )
    comps.append(ComponentHealth(name="Razorpay", status=rzp_status, detail=rzp_detail))
    ocr = (getattr(settings, "OCR_PROVIDER", "") or "").strip()
    comps.append(
        ComponentHealth(
            name="OCR provider",
            status="ok" if ocr else "not_configured",
            detail="Configured" if ocr else "Manual list entry only",
        )
    )
    quarantined = (
        await db.execute(
            select(func.count()).where(DataQuarantine.restored_at.is_(None))
        )
    ).scalar() or 0
    return SystemHealth(
        components=comps,
        outbox_pending=int(pending or 0),
        outbox_failed=int(failed or 0),
        oldest_pending_event_seconds=oldest_s,
        background_jobs=dict(JOB_STATUS),
        quarantined_test_records=int(quarantined),
        checked_at=now,
    )
