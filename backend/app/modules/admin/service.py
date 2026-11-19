import datetime
import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.modules.admin.schemas import (
    AdminCatalogueProductCreateRequest,
    AdminCatalogueProductDetailResponse,
    AdminCatalogueProductListItem,
    AdminCatalogueProductUpdateRequest,
    AdminCatalogueVariantCreateRequest,
    AdminCatalogueVariantItem,
    AdminCatalogueVariantUpdateRequest,
    AdminCategoryCreateRequest,
    AdminCategoryListItem,
    AdminDealCreateRequest,
    AdminDealDetailResponse,
    AdminDealListItem,
    AdminDealUpdateRequest,
    AdminOverviewResponse,
    AdminRetailerDetailResponse,
    AdminRetailerListItem,
    DocumentVerifyRequest,
    RetailerDocumentItem,
    RetailerVerificationHistoryItem,
    RetailerVerifyRequest,
)
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    RetailerVerificationDocument,
    RetailerVerificationHistory,
)
from app.modules.identity.models import User
from app.modules.orders.models import Order
from app.modules.pricing.models import Discount


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", cleaned)


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ================= Overview =================

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

    # ================= Retailer Verification & Approval =================

    async def list_retailers(
        self, status: str | None = None
    ) -> list[AdminRetailerListItem]:
        stmt = (
            select(
                Retailer,
                User.full_name.label("owner_name"),
                User.email.label("owner_email"),
                func.count(RetailerVerificationDocument.id).label("doc_count"),
            )
            .outerjoin(User, Retailer.user_id == User.id)
            .outerjoin(
                RetailerVerificationDocument,
                Retailer.id == RetailerVerificationDocument.retailer_id,
            )
            .group_by(Retailer.id, User.full_name, User.email)
            .order_by(Retailer.created_at.desc())
        )
        if status and status.upper() != "ALL":
            stmt = stmt.where(Retailer.verification_status == status.upper())

        rows = (await self.session.execute(stmt)).all()
        result = []
        for retailer, owner_name, owner_email, doc_count in rows:
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
                documents_count=doc_count or 0,
                created_at=retailer.created_at,
            )
            result.append(item)
        return result

    async def get_retailer(self, retailer_id: uuid.UUID) -> AdminRetailerDetailResponse:
        stmt = (
            select(
                Retailer,
                User.full_name.label("owner_name"),
                User.email.label("owner_email"),
            )
            .outerjoin(User, Retailer.user_id == User.id)
            .options(
                selectinload(Retailer.documents),
                selectinload(Retailer.verification_history),
            )
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

        docs = [
            RetailerDocumentItem(
                id=d.id,
                document_type=d.document_type,
                document_url=d.document_url,
                status=d.status,
                rejection_reason=d.rejection_reason,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in retailer.documents
        ]

        history = [
            RetailerVerificationHistoryItem(
                id=h.id,
                action=h.action,
                from_status=h.from_status,
                to_status=h.to_status,
                reason=h.reason,
                admin_id=h.admin_id,
                created_at=h.created_at,
            )
            for h in retailer.verification_history
        ]

        return AdminRetailerDetailResponse(
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
            description=retailer.description,
            logo_url=retailer.logo_url,
            rating=retailer.rating,
            owner_name=owner_name,
            owner_email=owner_email,
            reviewed_by_user_id=retailer.reviewed_by_user_id,
            verified_at=retailer.verified_at,
            rejection_reason=retailer.rejection_reason,
            created_at=retailer.created_at,
            documents=docs,
            verification_history=history,
        )

    async def verify_retailer(
        self,
        retailer_id: uuid.UUID,
        req: RetailerVerifyRequest,
        admin: User | None = None,
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
        from_status = retailer.verification_status
        to_status = req.status

        action = (
            "APPROVED"
            if to_status == "VERIFIED"
            else "REJECTED"
            if to_status == "REJECTED"
            else "SUSPENDED"
        )

        now = datetime.datetime.now(datetime.UTC)
        retailer.verification_status = to_status
        retailer.reviewed_by_user_id = admin.id if admin else None
        retailer.verified_at = now
        retailer.rejection_reason = req.rejection_reason

        if to_status in ("SUSPENDED", "REJECTED"):
            retailer.is_active = False
        elif to_status == "VERIFIED":
            retailer.is_active = True

        # Record verification audit trail
        history_entry = RetailerVerificationHistory(
            id=uuid.uuid4(),
            retailer_id=retailer.id,
            admin_id=admin.id if admin else None,
            action=action,
            from_status=from_status,
            to_status=to_status,
            reason=req.rejection_reason,
            created_at=now,
        )
        self.session.add(history_entry)
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
            documents_count=0,
            created_at=retailer.created_at,
        )

    async def verify_document(
        self,
        retailer_id: uuid.UUID,
        document_id: uuid.UUID,
        req: DocumentVerifyRequest,
    ) -> RetailerDocumentItem:
        stmt = select(RetailerVerificationDocument).where(
            RetailerVerificationDocument.id == document_id,
            RetailerVerificationDocument.retailer_id == retailer_id,
        )
        doc = (await self.session.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise AppException(
                code="DOCUMENT_NOT_FOUND",
                message="Verification document not found for this retailer.",
                status_code=404,
            )

        doc.status = req.status
        doc.rejection_reason = req.rejection_reason
        await self.session.flush()
        await self.session.refresh(doc)

        return RetailerDocumentItem(
            id=doc.id,
            document_type=doc.document_type,
            document_url=doc.document_url,
            status=doc.status,
            rejection_reason=doc.rejection_reason,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    # ================= Admin Catalogue Management =================

    async def list_catalogue_products(
        self,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        brand: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminCatalogueProductListItem]:
        stmt = (
            select(
                Product,
                Category.name.label("category_name"),
                func.count(func.distinct(ProductVariant.id)).label("var_count"),
                func.count(func.distinct(ProductListing.id)).label("list_count"),
            )
            .join(Category, Product.category_id == Category.id)
            .outerjoin(ProductVariant, Product.id == ProductVariant.product_id)
            .outerjoin(ProductListing, ProductVariant.id == ProductListing.variant_id)
            .options(selectinload(Product.images))
            .group_by(Product.id, Category.name)
            .order_by(Product.created_at.desc())
        )

        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if brand and brand.strip():
            stmt = stmt.where(func.lower(Product.brand) == brand.strip().lower())
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Product.name).like(term),
                    func.lower(Product.brand).like(term),
                    func.lower(Product.slug).like(term),
                )
            )

        stmt = stmt.limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).all()

        results = []
        for prod, cat_name, var_count, list_count in rows:
            primary_img = next((img.url for img in prod.images if img.is_primary), None)
            if not primary_img and prod.images:
                primary_img = prod.images[0].url

            results.append(
                AdminCatalogueProductListItem(
                    id=prod.id,
                    name=prod.name,
                    slug=prod.slug,
                    brand=prod.brand,
                    category_id=prod.category_id,
                    category_name=cat_name,
                    is_active=prod.is_active,
                    variants_count=var_count or 0,
                    listings_count=list_count or 0,
                    primary_image_url=primary_img,
                    created_at=prod.created_at,
                )
            )
        return results

    async def get_catalogue_product(
        self, product_id: uuid.UUID
    ) -> AdminCatalogueProductDetailResponse:
        stmt = (
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.images),
                selectinload(Product.variants).selectinload(ProductVariant.listings),
            )
            .where(Product.id == product_id)
        )
        prod = (await self.session.execute(stmt)).scalar_one_or_none()
        if not prod:
            raise AppException(
                code="PRODUCT_NOT_FOUND",
                message="Catalogue product not found.",
                status_code=404,
            )

        variants = []
        total_active_listings = 0
        for v in prod.variants:
            active_listings = sum(1 for listing in v.listings if listing.is_active)
            total_active_listings += active_listings
            variants.append(
                AdminCatalogueVariantItem(
                    id=v.id,
                    product_id=v.product_id,
                    name=v.name,
                    sku=v.sku,
                    attributes=v.attributes or {},
                    is_active=v.is_active,
                    created_at=v.created_at,
                    listings_count=len(v.listings),
                )
            )

        images = [
            {
                "id": str(img.id),
                "url": img.url,
                "alt_text": img.alt_text,
                "is_primary": img.is_primary,
                "sort_order": img.sort_order,
            }
            for img in prod.images
        ]

        return AdminCatalogueProductDetailResponse(
            id=prod.id,
            name=prod.name,
            slug=prod.slug,
            brand=prod.brand,
            category_id=prod.category_id,
            category_name=prod.category.name if prod.category else None,
            description=prod.description,
            is_active=prod.is_active,
            created_at=prod.created_at,
            updated_at=prod.updated_at,
            images=images,
            variants=variants,
            active_listings_count=total_active_listings,
        )

    async def create_catalogue_product(
        self, req: AdminCatalogueProductCreateRequest
    ) -> AdminCatalogueProductDetailResponse:
        # 1. Verify category exists
        cat_stmt = select(Category).where(Category.id == req.category_id)
        cat = (await self.session.execute(cat_stmt)).scalar_one_or_none()
        if not cat:
            raise AppException(
                code="CATEGORY_NOT_FOUND",
                message="Selected category does not exist.",
                status_code=404,
            )

        # 2. Determine unique slug
        base_slug = req.slug.strip() if req.slug else _slugify(req.name)
        slug = base_slug
        existing_slug = (
            await self.session.execute(select(Product.id).where(Product.slug == slug))
        ).scalar_one_or_none()
        if existing_slug:
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # 3. Check SKU uniqueness for initial variants
        for v_req in req.variants:
            existing_sku = (
                await self.session.execute(
                    select(ProductVariant.id).where(ProductVariant.sku == v_req.sku)
                )
            ).scalar_one_or_none()
            if existing_sku:
                raise AppException(
                    code="DUPLICATE_SKU",
                    message=f"Variant SKU '{v_req.sku}' is already in use by another catalogue variant.",
                    status_code=409,
                )

        prod = Product(
            id=uuid.uuid4(),
            category_id=req.category_id,
            name=req.name.strip(),
            slug=slug,
            brand=req.brand.strip(),
            description=req.description.strip() if req.description else None,
            is_active=req.is_active,
        )
        self.session.add(prod)
        await self.session.flush()

        # Add images
        for idx, img_url in enumerate(req.image_urls):
            img = ProductImage(
                id=uuid.uuid4(),
                product_id=prod.id,
                url=img_url,
                alt_text=prod.name,
                is_primary=(idx == 0),
                sort_order=idx,
            )
            self.session.add(img)

        # Add initial variants (or create a standard default variant if none provided)
        variants_to_create = req.variants
        if not variants_to_create:
            default_sku = f"{_slugify(prod.brand)[:4].upper()}-{_slugify(prod.name)[:6].upper()}-{uuid.uuid4().hex[:4].upper()}"
            variants_to_create = [
                AdminCatalogueVariantCreateRequest(
                    name="Standard",
                    sku=default_sku,
                    attributes={"model": "Standard"},
                    is_active=True,
                )
            ]

        for v_req in variants_to_create:
            variant = ProductVariant(
                id=uuid.uuid4(),
                product_id=prod.id,
                name=v_req.name.strip(),
                sku=v_req.sku.strip(),
                attributes=v_req.attributes or {},
                is_active=v_req.is_active,
            )
            self.session.add(variant)

        await self.session.flush()
        return await self.get_catalogue_product(prod.id)

    async def update_catalogue_product(
        self, product_id: uuid.UUID, req: AdminCatalogueProductUpdateRequest
    ) -> AdminCatalogueProductDetailResponse:
        prod = (
            await self.session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if not prod:
            raise AppException(
                code="PRODUCT_NOT_FOUND",
                message="Catalogue product not found.",
                status_code=404,
            )

        if req.category_id is not None:
            cat = (
                await self.session.execute(
                    select(Category).where(Category.id == req.category_id)
                )
            ).scalar_one_or_none()
            if not cat:
                raise AppException(
                    code="CATEGORY_NOT_FOUND",
                    message="Selected category does not exist.",
                    status_code=404,
                )
            prod.category_id = req.category_id

        if req.name is not None:
            prod.name = req.name.strip()
        if req.brand is not None:
            prod.brand = req.brand.strip()
        if req.description is not None:
            prod.description = req.description.strip() if req.description else None
        if req.is_active is not None:
            prod.is_active = req.is_active
        if req.slug is not None and req.slug.strip() != prod.slug:
            new_slug = req.slug.strip()
            existing = (
                await self.session.execute(
                    select(Product.id).where(
                        Product.slug == new_slug, Product.id != product_id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                raise AppException(
                    code="SLUG_ALREADY_EXISTS",
                    message=f"Product slug '{new_slug}' is already taken.",
                    status_code=409,
                )
            prod.slug = new_slug

        await self.session.flush()
        return await self.get_catalogue_product(product_id)

    async def delete_catalogue_product(self, product_id: uuid.UUID) -> None:
        prod = (
            await self.session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if not prod:
            raise AppException(
                code="PRODUCT_NOT_FOUND",
                message="Catalogue product not found.",
                status_code=404,
            )

        # Deactivate product to preserve immutable order line item histories
        prod.is_active = False
        await self.session.flush()

    async def create_variant(
        self, product_id: uuid.UUID, req: AdminCatalogueVariantCreateRequest
    ) -> AdminCatalogueVariantItem:
        prod = (
            await self.session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        if not prod:
            raise AppException(
                code="PRODUCT_NOT_FOUND",
                message="Catalogue product not found.",
                status_code=404,
            )

        # Check SKU uniqueness
        sku = req.sku.strip()
        existing = (
            await self.session.execute(
                select(ProductVariant.id).where(ProductVariant.sku == sku)
            )
        ).scalar_one_or_none()
        if existing:
            raise AppException(
                code="DUPLICATE_SKU",
                message=f"Variant SKU '{sku}' is already in use by another catalogue variant.",
                status_code=409,
            )

        variant = ProductVariant(
            id=uuid.uuid4(),
            product_id=product_id,
            name=req.name.strip(),
            sku=sku,
            attributes=req.attributes or {},
            is_active=req.is_active,
        )
        self.session.add(variant)
        await self.session.flush()

        return AdminCatalogueVariantItem(
            id=variant.id,
            product_id=variant.product_id,
            name=variant.name,
            sku=variant.sku,
            attributes=variant.attributes,
            is_active=variant.is_active,
            created_at=variant.created_at,
            listings_count=0,
        )

    async def update_variant(
        self, variant_id: uuid.UUID, req: AdminCatalogueVariantUpdateRequest
    ) -> AdminCatalogueVariantItem:
        variant = (
            await self.session.execute(
                select(ProductVariant)
                .options(selectinload(ProductVariant.listings))
                .where(ProductVariant.id == variant_id)
            )
        ).scalar_one_or_none()
        if not variant:
            raise AppException(
                code="VARIANT_NOT_FOUND",
                message="Catalogue variant not found.",
                status_code=404,
            )

        if req.name is not None:
            variant.name = req.name.strip()
        if req.attributes is not None:
            variant.attributes = req.attributes
        if req.is_active is not None:
            variant.is_active = req.is_active
        if req.sku is not None and req.sku.strip() != variant.sku:
            new_sku = req.sku.strip()
            existing = (
                await self.session.execute(
                    select(ProductVariant.id).where(
                        ProductVariant.sku == new_sku, ProductVariant.id != variant_id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                raise AppException(
                    code="DUPLICATE_SKU",
                    message=f"Variant SKU '{new_sku}' is already in use by another catalogue variant.",
                    status_code=409,
                )
            variant.sku = new_sku

        await self.session.flush()
        return AdminCatalogueVariantItem(
            id=variant.id,
            product_id=variant.product_id,
            name=variant.name,
            sku=variant.sku,
            attributes=variant.attributes,
            is_active=variant.is_active,
            created_at=variant.created_at,
            listings_count=len(variant.listings),
        )

    async def delete_variant(self, variant_id: uuid.UUID) -> None:
        variant = (
            await self.session.execute(
                select(ProductVariant).where(ProductVariant.id == variant_id)
            )
        ).scalar_one_or_none()
        if not variant:
            raise AppException(
                code="VARIANT_NOT_FOUND",
                message="Catalogue variant not found.",
                status_code=404,
            )

        variant.is_active = False
        await self.session.flush()

    # ================= Category Management =================

    async def list_categories(self) -> list[AdminCategoryListItem]:
        stmt = (
            select(
                Category,
                func.count(Product.id).label("prod_count"),
            )
            .outerjoin(Product, Category.id == Product.category_id)
            .group_by(Category.id)
            .order_by(Category.name.asc())
        )
        rows = (await self.session.execute(stmt)).all()

        cat_map: dict[uuid.UUID, AdminCategoryListItem] = {}
        for cat, prod_count in rows:
            cat_map[cat.id] = AdminCategoryListItem(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                image_url=cat.image_url,
                icon=cat.icon,
                parent_id=cat.parent_id,
                is_active=cat.is_active,
                product_count=prod_count or 0,
                children=[],
            )

        root_categories: list[AdminCategoryListItem] = []
        for cat_item in cat_map.values():
            if cat_item.parent_id and cat_item.parent_id in cat_map:
                cat_item.parent_name = cat_map[cat_item.parent_id].name
                cat_map[cat_item.parent_id].children.append(cat_item)
            else:
                root_categories.append(cat_item)

        return root_categories

    async def create_category(
        self, req: AdminCategoryCreateRequest
    ) -> AdminCategoryListItem:
        base_slug = req.slug.strip() if req.slug else _slugify(req.name)
        slug = base_slug
        existing = (
            await self.session.execute(select(Category.id).where(Category.slug == slug))
        ).scalar_one_or_none()
        if existing:
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        if req.parent_id:
            parent = (
                await self.session.execute(
                    select(Category).where(Category.id == req.parent_id)
                )
            ).scalar_one_or_none()
            if not parent:
                raise AppException(
                    code="PARENT_CATEGORY_NOT_FOUND",
                    message="Parent category not found.",
                    status_code=404,
                )

        cat = Category(
            id=uuid.uuid4(),
            name=req.name.strip(),
            slug=slug,
            description=req.description.strip() if req.description else None,
            image_url=req.image_url.strip() if req.image_url else None,
            icon=req.icon.strip() if req.icon else None,
            parent_id=req.parent_id,
            is_active=req.is_active,
        )
        self.session.add(cat)
        await self.session.flush()

        return AdminCategoryListItem(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            image_url=cat.image_url,
            icon=cat.icon,
            parent_id=cat.parent_id,
            is_active=cat.is_active,
            product_count=0,
            children=[],
        )

    # ================= Platform Deals & Promotions =================

    async def list_deals(
        self,
        status_filter: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminDealListItem]:
        stmt = (
            select(
                Discount,
                Category.name.label("category_name"),
                Product.name.label("product_name"),
            )
            .outerjoin(Category, Discount.category_id == Category.id)
            .outerjoin(Product, Discount.product_id == Product.id)
            .order_by(Discount.created_at.desc())
        )

        if scope and scope.upper() != "ALL":
            stmt = stmt.where(Discount.scope == scope.upper())

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Discount.name).like(term),
                    func.lower(Discount.code).like(term),
                )
            )

        rows = (await self.session.execute(stmt.limit(limit).offset(offset))).all()
        now = datetime.datetime.now(datetime.UTC)

        results = []
        for discount, cat_name, prod_name in rows:
            if not discount.is_active:
                deal_status = "PAUSED"
            elif discount.valid_to and discount.valid_to < now:
                deal_status = "EXPIRED"
            elif discount.valid_from > now:
                deal_status = "SCHEDULED"
            else:
                deal_status = "ACTIVE"

            if status_filter and status_filter.upper() != "ALL":
                if deal_status != status_filter.upper():
                    continue

            results.append(
                AdminDealListItem(
                    id=discount.id,
                    name=discount.name,
                    code=discount.code,
                    discount_type=discount.discount_type,
                    discount_value=discount.discount_value,
                    scope=discount.scope,
                    category_id=discount.category_id,
                    category_name=cat_name,
                    product_id=discount.product_id,
                    product_name=prod_name,
                    listing_id=discount.listing_id,
                    min_order_paise=discount.min_order_paise,
                    max_discount_paise=discount.max_discount_paise,
                    usage_limit=discount.usage_limit,
                    times_used=discount.times_used,
                    is_active=discount.is_active,
                    valid_from=discount.valid_from,
                    valid_to=discount.valid_to,
                    status=deal_status,
                    created_at=discount.created_at,
                )
            )
        return results

    async def get_deal(self, deal_id: uuid.UUID) -> AdminDealDetailResponse:
        stmt = (
            select(
                Discount,
                Category.name.label("category_name"),
                Product.name.label("product_name"),
            )
            .outerjoin(Category, Discount.category_id == Category.id)
            .outerjoin(Product, Discount.product_id == Product.id)
            .where(Discount.id == deal_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if not row:
            raise AppException(
                code="DEAL_NOT_FOUND",
                message="Platform deal not found.",
                status_code=404,
            )

        discount, cat_name, prod_name = row[0], row[1], row[2]
        now = datetime.datetime.now(datetime.UTC)
        if not discount.is_active:
            deal_status = "PAUSED"
        elif discount.valid_to and discount.valid_to < now:
            deal_status = "EXPIRED"
        elif discount.valid_from > now:
            deal_status = "SCHEDULED"
        else:
            deal_status = "ACTIVE"

        return AdminDealDetailResponse(
            id=discount.id,
            name=discount.name,
            code=discount.code,
            discount_type=discount.discount_type,
            discount_value=discount.discount_value,
            scope=discount.scope,
            category_id=discount.category_id,
            category_name=cat_name,
            product_id=discount.product_id,
            product_name=prod_name,
            listing_id=discount.listing_id,
            min_order_paise=discount.min_order_paise,
            max_discount_paise=discount.max_discount_paise,
            usage_limit=discount.usage_limit,
            times_used=discount.times_used,
            is_active=discount.is_active,
            valid_from=discount.valid_from,
            valid_to=discount.valid_to,
            status=deal_status,
            description=discount.description,
            created_at=discount.created_at,
            updated_at=discount.updated_at,
        )

    async def create_deal(self, req: AdminDealCreateRequest) -> AdminDealDetailResponse:
        # Validate coupon code uniqueness if provided
        if req.code and req.code.strip():
            code_clean = req.code.strip().upper()
            existing = (
                await self.session.execute(
                    select(Discount.id).where(Discount.code == code_clean)
                )
            ).scalar_one_or_none()
            if existing:
                raise AppException(
                    code="COUPON_CODE_ALREADY_EXISTS",
                    message=f"Discount code '{code_clean}' already exists.",
                    status_code=409,
                )
        else:
            code_clean = None

        # Validate target existences based on scope
        if req.scope == "CATEGORY" and req.category_id:
            cat = (
                await self.session.execute(
                    select(Category.id).where(Category.id == req.category_id)
                )
            ).scalar_one_or_none()
            if not cat:
                raise AppException(
                    code="CATEGORY_NOT_FOUND",
                    message="Target category not found for deal.",
                    status_code=404,
                )
        elif req.scope == "PRODUCT" and req.product_id:
            prod = (
                await self.session.execute(
                    select(Product.id).where(Product.id == req.product_id)
                )
            ).scalar_one_or_none()
            if not prod:
                raise AppException(
                    code="PRODUCT_NOT_FOUND",
                    message="Target product not found for deal.",
                    status_code=404,
                )
        elif req.scope == "LISTING" and req.listing_id:
            listing = (
                await self.session.execute(
                    select(ProductListing.id).where(ProductListing.id == req.listing_id)
                )
            ).scalar_one_or_none()
            if not listing:
                raise AppException(
                    code="LISTING_NOT_FOUND",
                    message="Target listing not found for deal.",
                    status_code=404,
                )

        deal = Discount(
            id=uuid.uuid4(),
            code=code_clean,
            name=req.name.strip(),
            discount_type=req.discount_type,
            discount_value=req.discount_value,
            scope=req.scope,
            category_id=req.category_id if req.scope == "CATEGORY" else None,
            product_id=req.product_id if req.scope == "PRODUCT" else None,
            listing_id=req.listing_id if req.scope == "LISTING" else None,
            min_order_paise=req.min_order_paise,
            max_discount_paise=req.max_discount_paise,
            usage_limit=req.usage_limit,
            times_used=0,
            valid_from=req.valid_from,
            valid_to=req.valid_to,
            description=req.description.strip() if req.description else None,
            is_active=req.is_active,
        )
        self.session.add(deal)
        await self.session.flush()

        return await self.get_deal(deal.id)

    async def update_deal(
        self, deal_id: uuid.UUID, req: AdminDealUpdateRequest
    ) -> AdminDealDetailResponse:
        deal = (
            await self.session.execute(select(Discount).where(Discount.id == deal_id))
        ).scalar_one_or_none()
        if not deal:
            raise AppException(
                code="DEAL_NOT_FOUND",
                message="Platform deal not found.",
                status_code=404,
            )

        if req.name is not None:
            deal.name = req.name.strip()
        if req.code is not None:
            code_clean = req.code.strip().upper() if req.code.strip() else None
            if code_clean and code_clean != deal.code:
                existing = (
                    await self.session.execute(
                        select(Discount.id).where(
                            Discount.code == code_clean, Discount.id != deal_id
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    raise AppException(
                        code="COUPON_CODE_ALREADY_EXISTS",
                        message=f"Discount code '{code_clean}' already exists.",
                        status_code=409,
                    )
            deal.code = code_clean

        if req.discount_type is not None:
            deal.discount_type = req.discount_type
        if req.discount_value is not None:
            if deal.discount_type == "PERCENTAGE" and req.discount_value > 9000:
                raise AppException(
                    code="INVALID_DISCOUNT_VALUE",
                    message="Percentage discount cannot exceed 9000 basis points (90%).",
                    status_code=400,
                )
            deal.discount_value = req.discount_value
        if req.min_order_paise is not None:
            deal.min_order_paise = req.min_order_paise
        if req.max_discount_paise is not None:
            deal.max_discount_paise = req.max_discount_paise
        if req.usage_limit is not None:
            deal.usage_limit = req.usage_limit
        if req.valid_from is not None:
            deal.valid_from = req.valid_from
        if req.valid_to is not None:
            deal.valid_to = req.valid_to
        if req.description is not None:
            deal.description = req.description.strip() if req.description else None
        if req.is_active is not None:
            deal.is_active = req.is_active

        await self.session.flush()
        return await self.get_deal(deal_id)

    async def delete_deal(self, deal_id: uuid.UUID) -> None:
        deal = (
            await self.session.execute(select(Discount).where(Discount.id == deal_id))
        ).scalar_one_or_none()
        if not deal:
            raise AppException(
                code="DEAL_NOT_FOUND",
                message="Platform deal not found.",
                status_code=404,
            )

        deal.is_active = False
        await self.session.flush()
