"""BASKET — demonstration marketplace data (development / demo databases only).

Builds on ``seed_phase1_demo`` (accounts, 10 departments, curated products,
two stores, sample paid order) and adds what a live demonstration needs:

* two more clearly-labelled *fictional* demo stores (``retailer3/4@basket.demo``)
  cross-listing popular products at their own prices, so price comparison,
  RFQ bidding and Dukaan vs Dukaan have genuine competition;
* active and expired store offers (percentages stored in basis points) and a
  platform deal, with Sale Stream flash deals created by the normal service;
* 45 days of price history per listing, stored with ``source='DEMO_SEED'`` so
  the API and UI always label it as demonstration data;
* retailer group-buy templates and negotiation rules;
* one open customer RFQ with a real bid, one customer-started group buy and
  one unmet-demand request — all created through the regular services by the
  demo accounts (no fabricated participants or reviews).

Every demo account uses the ``@basket.demo`` domain and the documented demo
password. Re-running is safe (idempotent). Refuses to run in production.

Usage (from backend/):  python -m app.seeds.seed_demo_marketplace
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.community.models import GroupBuyCampaign, GroupBuyTemplate
from app.modules.exchange.models import ExchangeRequest
from app.modules.identity.models import User
from app.modules.identity.security import hash_password
from app.modules.negotiation.models import RetailerNegotiationRule
from app.modules.price_intel.models import PriceHistoryTick
from app.modules.price_intel.service import record_price_tick
from app.modules.pricing.models import Discount
from app.seeds.seed_phase1_demo import seed_phase1_demo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_demo_marketplace")

DEMO_PASSWORD = "Basket@123"

EXTRA_STORES = [
    {
        "email": "retailer3@basket.demo",
        "full_name": "Namma Digital Store Desk",
        "store_name": "Namma Digital Store",
        "slug": "namma-digital-store",
        "description": "Demonstration store (fictional) for consumer electronics and appliances.",
        "business_address": "Demo address — 1st Main, Jayanagar 4th Block, Bengaluru, Karnataka - 560011",
        "phone": "+919800000013",
        "state": "KA",
        "service_pincodes": [],
        "categories": ["electronics", "home-kitchen"],
        "price_factor_bps": 9650,  # ~3.5% cheaper than the reference store
    },
    {
        "email": "retailer4@basket.demo",
        "full_name": "Ghar Ghar Essentials Desk",
        "store_name": "Ghar Ghar Essentials",
        "slug": "ghar-ghar-essentials",
        "description": "Demonstration store (fictional) for groceries, home and personal care.",
        "business_address": "Demo address — Andheri East, Mumbai, Maharashtra - 400069",
        "phone": "+919800000014",
        "state": "MH",
        "service_pincodes": [],
        "categories": ["grocery-food", "home-kitchen", "beauty-personal-care"],
        "price_factor_bps": 10300,  # ~3% dearer
    },
]


def _stable_unit(*parts: str) -> float:
    """Deterministic 0..1 value so re-runs produce identical demo history."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _verify_safe() -> None:
    if settings.is_production:
        raise RuntimeError("Demo seed refuses to run in production.")


async def _ensure_store(session, spec: dict) -> Retailer:
    user = (
        await session.execute(select(User).where(User.email == spec["email"]))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=spec["email"],
            full_name=spec["full_name"],
            phone=spec["phone"],
            hashed_password=hash_password(DEMO_PASSWORD),
            role="retailer",
            is_active=True,
        )
        session.add(user)
        await session.flush()
    ret = (
        await session.execute(select(Retailer).where(Retailer.slug == spec["slug"]))
    ).scalar_one_or_none()
    if ret is None:
        ret = Retailer(
            id=uuid.uuid4(),
            user_id=user.id,
            name=spec["store_name"],
            slug=spec["slug"],
            description=spec["description"],
            business_address=spec["business_address"],
            contact_phone=spec["phone"],
            contact_email=spec["email"],
            state=spec["state"],
            state_source="DEMO_SEED",
            verification_status="VERIFIED",
            is_active=True,
            is_open=True,
            service_pincodes=spec["service_pincodes"],
        )
        session.add(ret)
        await session.flush()
    ret.user_id = user.id
    ret.is_active = True
    ret.is_open = True
    ret.verification_status = "VERIFIED"
    return ret


async def _cross_list(session, ret: Retailer, spec: dict) -> int:
    """List the reference store's products in the given departments at this
    store's own price."""
    from app.modules.catalogue.models import Category

    created = 0
    ref_listings = (
        await session.execute(
            select(ProductListing, ProductVariant, Product)
            .join(ProductVariant, ProductVariant.id == ProductListing.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(Category, Category.id == Product.category_id)
            .join(Retailer, Retailer.id == ProductListing.retailer_id)
            .where(
                Category.slug.in_(spec["categories"]),
                Retailer.slug.in_(["basket-mart", "basket-lifestyle"]),
                ProductListing.is_active.is_(True),
                Product.is_active.is_(True),
            )
        )
    ).all()
    for ref, variant, _product in ref_listings:
        exists = (
            await session.execute(
                select(ProductListing.id).where(
                    ProductListing.retailer_id == ret.id,
                    ProductListing.variant_id == variant.id,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        jitter = int(_stable_unit(spec["slug"], str(variant.id)) * 300) - 150  # ±1.5%
        price = (
            int(ref.selling_price_paise) * (spec["price_factor_bps"] + jitter) // 10000
        )
        price = max(100, (price // 100) * 100 - 1 if price > 1000 else price)
        price = min(price, int(ref.original_price_paise))
        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=ret.id,
            variant_id=variant.id,
            seller_sku=f"{spec['slug'][:6].upper()}-{variant.sku}"[:100],
            original_price_paise=int(ref.original_price_paise),
            selling_price_paise=price,
            currency="INR",
            hsn_code=ref.hsn_code,
            gst_rate_basis_points=ref.gst_rate_basis_points,
            tax_classification_source=ref.tax_classification_source,
            is_tax_verified=ref.is_tax_verified,
            is_active=True,
        )
        session.add(listing)
        await session.flush()
        stock = 5 + int(_stable_unit("stock", spec["slug"], str(variant.id)) * 40)
        session.add(
            StoreInventory(
                id=uuid.uuid4(),
                listing_id=listing.id,
                on_hand_quantity=stock,
                reserved_quantity=0,
            )
        )
        created += 1
    await session.flush()
    return created


async def _demo_price_history(session, days: int = 45) -> int:
    """Deterministic DEMO_SEED history ending yesterday; never overwrites LIVE rows."""
    today = datetime.now(UTC).date()
    listings = (
        (
            await session.execute(
                select(ProductListing).where(ProductListing.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    written = 0
    for lst in listings:
        existing = set(
            (
                await session.execute(
                    select(PriceHistoryTick.recorded_date).where(
                        PriceHistoryTick.listing_id == lst.id
                    )
                )
            ).scalars()
        )
        base = int(lst.selling_price_paise)
        for back in range(days, 0, -1):
            day: date = today - timedelta(days=back)
            if day in existing:
                continue
            u = _stable_unit("hist", str(lst.id), day.isoformat())
            # Mild random walk within ±6% of today's price; a few listings show a
            # genuine recent drop so discount badges have something to evaluate.
            drift = (u - 0.5) * 0.12
            if _stable_unit("drop", str(lst.id)) < 0.25 and back > 10:
                drift += 0.08
            price = max(100, int(base * (1 + drift)))
            await record_price_tick(
                session,
                listing_id=lst.id,
                selling_price_paise=price,
                mrp_paise=int(lst.original_price_paise),
                on=day,
                source="DEMO_SEED",
            )
            written += 1
    await session.flush()
    return written


async def _offers(session, stores: dict[str, Retailer]) -> None:
    from app.modules.retailer.schemas import RetailerOfferCreateRequest
    from app.modules.retailer.service import RetailerService

    now = datetime.now(UTC)
    for slug, ret in stores.items():
        scope = f"RET_{ret.id.hex[:24]}"
        have = (
            await session.execute(select(func.count()).where(Discount.scope == scope))
        ).scalar() or 0
        if have:
            continue
        svc = RetailerService(session)
        code = slug.replace("-", "")[:6].upper()
        await svc.create_offer(
            ret,
            RetailerOfferCreateRequest(
                code=f"{code}10",
                name="10% off orders above ₹999",
                description="Store-wide demo offer.",
                discount_type="PERCENTAGE",
                discount_value=1000,
                min_order_paise=99900,
                max_discount_paise=50000,
                valid_to=now + timedelta(days=30),
            ),
        )
        # Expired offer (kept for history / "expired" filters).
        expired = await svc.create_offer(
            ret,
            RetailerOfferCreateRequest(
                code=f"{code}FEST",
                name="Festive ₹150 off (ended)",
                description="Expired demo offer.",
                discount_type="FIXED_AMOUNT",
                discount_value=15000,
                min_order_paise=149900,
                valid_to=now + timedelta(days=1),
            ),
        )
        d = await session.get(Discount, expired.id)
        d.valid_from = now - timedelta(days=20)
        d.valid_to = now - timedelta(days=5)
        # Time-limited listing flash deal -> appears in Sale Stream.
        first = (
            await session.execute(
                select(ProductListing)
                .where(
                    ProductListing.retailer_id == ret.id,
                    ProductListing.is_active.is_(True),
                )
                .order_by(ProductListing.selling_price_paise.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if first:
            await svc.create_offer(
                ret,
                RetailerOfferCreateRequest(
                    name="Flash deal: 12% off for 3 days",
                    description="Time-limited demo flash deal.",
                    discount_type="PERCENTAGE",
                    discount_value=1200,
                    listing_id=first.id,
                    valid_to=now + timedelta(days=3),
                ),
            )
    await session.flush()


async def _rules_and_templates(session, stores: dict[str, Retailer]) -> None:
    for i, ret in enumerate(stores.values()):
        listings = (
            (
                await session.execute(
                    select(ProductListing)
                    .where(
                        ProductListing.retailer_id == ret.id,
                        ProductListing.is_active.is_(True),
                    )
                    .order_by(ProductListing.selling_price_paise.desc())
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
        has_rule = (
            await session.execute(
                select(func.count()).where(
                    RetailerNegotiationRule.retailer_id == ret.id
                )
            )
        ).scalar() or 0
        if not has_rule:
            session.add(
                RetailerNegotiationRule(
                    id=uuid.uuid4(),
                    retailer_id=ret.id,
                    listing_id=None,
                    max_auto_discount_bps=500 + 100 * i,
                    bundle_quantity_threshold=3,
                    bundle_extra_discount_bps=200,
                    is_active=True,
                )
            )
        for lst in listings[:2]:
            t = (
                await session.execute(
                    select(GroupBuyTemplate).where(
                        GroupBuyTemplate.listing_id == lst.id,
                        GroupBuyTemplate.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if t is None:
                session.add(
                    GroupBuyTemplate(
                        id=uuid.uuid4(),
                        retailer_id=ret.id,
                        listing_id=lst.id,
                        min_participants=3,
                        max_participants=10,
                        discount_bps=800,
                        duration_hours=72,
                        max_quantity_per_member=2,
                        max_open_campaigns=3,
                        is_active=True,
                    )
                )
    await session.flush()


async def _customer_activity(session) -> None:
    """Real actions by the demo customer through the normal services."""
    from app.modules.community.schemas import CustomerStartRequest
    from app.modules.community.service import CommunityBuyingService
    from app.modules.demand.service import DemandService
    from app.modules.exchange.schemas import (
        BidLineInput,
        BidSubmitRequest,
        ExchangeRequestCreate,
        ManifestItem,
    )
    from app.modules.exchange.service import ExchangeService

    cust = (
        await session.execute(select(User).where(User.email == "customer@basket.demo"))
    ).scalar_one()

    # Customer-started group buy (the customer is its only real member).
    has_campaign = (
        await session.execute(
            select(func.count()).where(GroupBuyCampaign.created_by_user_id == cust.id)
        )
    ).scalar() or 0
    if not has_campaign:
        t = (
            await session.execute(
                select(GroupBuyTemplate)
                .where(GroupBuyTemplate.is_active.is_(True))
                .limit(1)
            )
        ).scalar_one_or_none()
        if t:
            await CommunityBuyingService(session).start_by_customer(
                cust.id, CustomerStartRequest(template_id=t.id, quantity=1)
            )

    # Open RFQ with one genuine bid from a demo store.
    has_rfq = (
        await session.execute(
            select(func.count()).where(ExchangeRequest.user_id == cust.id)
        )
    ).scalar() or 0
    if not has_rfq:
        ex = ExchangeService(session)
        req = await ex.create_request(
            cust.id,
            ExchangeRequestCreate(
                title="Kitchen restock for a new flat",
                delivery_pincode="560038",
                budget_limit_paise=1_500_000,
                items=[
                    ManifestItem(name="Mixer grinder 750W", quantity=1),
                    ManifestItem(name="Electric kettle 1.5L", quantity=1),
                ],
                bidding_hours=72,
            ),
        )
        store = (
            await session.execute(
                select(Retailer).where(Retailer.slug == "namma-digital-store")
            )
        ).scalar_one_or_none()
        if store:
            lines = []
            for idx, needle in enumerate(["Mixer Grinder", "Kettle"]):
                lst = (
                    await session.execute(
                        select(ProductListing)
                        .join(
                            ProductVariant,
                            ProductVariant.id == ProductListing.variant_id,
                        )
                        .join(Product, Product.id == ProductVariant.product_id)
                        .where(
                            ProductListing.retailer_id == store.id,
                            Product.name.ilike(f"%{needle}%"),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if lst:
                    lines.append(
                        BidLineInput(
                            manifest_index=idx,
                            listing_id=lst.id,
                            unit_price_paise=int(lst.selling_price_paise) - 5000,
                        )
                    )
            if lines:
                await ex.submit_bid(
                    req.id,
                    store,
                    BidSubmitRequest(
                        lines=lines, estimated_delivery_hours=48, notes="Demo bid"
                    ),
                )

    # Unmet demand for something no store sells.
    await DemandService(session).record_signal(
        signal_type="WISHLIST",
        query_text="Dyson V12 Detect Slim vacuum",
        pincode="560038",
        user_id=cust.id,
    )
    await session.flush()


async def seed_demo_marketplace() -> None:
    _verify_safe()
    await seed_phase1_demo()
    async with get_session_factory()() as session:
        stores = {}
        for spec in EXTRA_STORES:
            ret = await _ensure_store(session, spec)
            n = await _cross_list(session, ret, spec)
            logger.info("Store %s: %d new listings", spec["store_name"], n)
            stores[spec["slug"]] = ret
        for slug in ("basket-mart", "basket-lifestyle"):
            r = (
                await session.execute(select(Retailer).where(Retailer.slug == slug))
            ).scalar_one()
            stores[slug] = r
        await session.commit()

        await _offers(session, stores)
        await session.commit()
        await _rules_and_templates(session, stores)
        await session.commit()
        n = await _demo_price_history(session)
        logger.info("Demo price history rows written: %d (source=DEMO_SEED)", n)
        await session.commit()
        await _customer_activity(session)
        await session.commit()
    logger.info("Demo marketplace ready. Accounts use password %s", DEMO_PASSWORD)


if __name__ == "__main__":
    asyncio.run(seed_demo_marketplace())
