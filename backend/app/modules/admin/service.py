import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.admin.schemas import (
    AdminOverviewResponse,
    AdminRetailerListItem,
    RetailerVerifyRequest,
)
from app.modules.catalogue.models import Product, Retailer
from app.modules.identity.models import User
from app.modules.orders.models import Order


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(self) -> AdminOverviewResponse:
        # Total orders & total revenue
        order_stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_payable_paise), 0),
        )
        order_res = (await self.session.execute(order_stmt)).one()
        total_orders, total_revenue = order_res[0], order_res[1]

        # Total registered customers
        cust_stmt = select(func.count(User.id)).where(User.role == "customer")
        total_customers = (await self.session.execute(cust_stmt)).scalar() or 0

        # Total retailers & pending verifications
        ret_stmt = select(
            func.count(Retailer.id),
            func.count().filter(Retailer.verification_status == "PENDING"),
        )
        ret_res = (await self.session.execute(ret_stmt)).one()
        total_retailers, pending_verifications = ret_res[0], ret_res[1]

        # Active products
        prod_stmt = select(func.count(Product.id)).where(Product.is_active.is_(True))
        active_products = (await self.session.execute(prod_stmt)).scalar() or 0

        return AdminOverviewResponse(
            total_orders=total_orders,
            total_revenue_paise=total_revenue,
            total_customers=total_customers,
            total_retailers=total_retailers,
            pending_verifications=pending_verifications,
            active_products=active_products,
        )

    async def list_retailers(
        self, status: str | None = None
    ) -> list[AdminRetailerListItem]:
        stmt = (
            select(
                Retailer,
                User.full_name.label("owner_name"),
                User.email.label("owner_email"),
            )
            .outerjoin(User, Retailer.user_id == User.id)
            .order_by(Retailer.created_at.desc())
        )
        if status:
            stmt = stmt.where(Retailer.verification_status == status.upper())

        rows = (await self.session.execute(stmt)).all()
        result = []
        for retailer, owner_name, owner_email in rows:
            item = AdminRetailerListItem(
                id=retailer.id,
                name=retailer.name,
                slug=retailer.slug,
                state=retailer.state,
                verification_status=retailer.verification_status,
                is_active=retailer.is_active,
                is_open=retailer.is_open,
                business_address=retailer.business_address,
                contact_phone=retailer.contact_phone,
                contact_email=retailer.contact_email,
                owner_name=owner_name,
                owner_email=owner_email,
                created_at=retailer.created_at,
            )
            result.append(item)
        return result

    async def verify_retailer(
        self, retailer_id: uuid.UUID, req: RetailerVerifyRequest
    ) -> AdminRetailerListItem:
        stmt = (
            select(
                Retailer,
                User.full_name.label("owner_name"),
                User.email.label("owner_email"),
            )
            .outerjoin(User, Retailer.user_id == User.id)
            .where(Retailer.id == retailer_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if not row:
            raise AppException(
                code="RETAILER_NOT_FOUND",
                message="Retailer not found.",
                status_code=404,
            )

        retailer, owner_name, owner_email = row[0], row[1], row[2]
        retailer.verification_status = req.status
        if req.status == "SUSPENDED":
            retailer.is_active = False
        elif req.status == "VERIFIED":
            retailer.is_active = True

        await self.session.flush()

        return AdminRetailerListItem(
            id=retailer.id,
            name=retailer.name,
            slug=retailer.slug,
            state=retailer.state,
            verification_status=retailer.verification_status,
            is_active=retailer.is_active,
            is_open=retailer.is_open,
            business_address=retailer.business_address,
            contact_phone=retailer.contact_phone,
            contact_email=retailer.contact_email,
            owner_name=owner_name,
            owner_email=owner_email,
            created_at=retailer.created_at,
        )
