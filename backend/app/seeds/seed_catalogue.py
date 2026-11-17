import asyncio
import uuid

from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.logging import logger, setup_logging
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)

RETAILERS_DATA = [
    {
        "name": "Reliance Digital",
        "slug": "reliance-digital",
        "description": "India's leading consumer electronics and home appliances destination.",
        "logo_url": "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "MH",
    },
    {
        "name": "Croma",
        "slug": "croma",
        "description": "Tata's premier multi-brand electronics megastore with guaranteed authenticity.",
        "logo_url": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "KA",
    },
    {
        "name": "Tata CLiQ Luxury",
        "slug": "tata-cliq",
        "description": "Curated lifestyle, apparel, and premium fashion brands delivered across India.",
        "logo_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=200&q=80",
        "rating": 4.6,
        "state": "MH",
    },
    {
        "name": "Nature's Basket",
        "slug": "natures-basket",
        "description": "Pioneering gourmet grocery, fresh farm staples, and organic artisanal foods.",
        "logo_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=200&q=80",
        "rating": 4.9,
        "state": "MH",
    },
    {
        "name": "FabIndia",
        "slug": "fabindia",
        "description": "Celebrated handcrafted apparel, home decor, and heritage lifestyle goods.",
        "logo_url": "https://images.unsplash.com/photo-1506152983158-b4a74a01c721?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "DL",
    },
    {
        "name": "Decathlon India",
        "slug": "decathlon-india",
        "description": "Comprehensive sporting equipment, outdoor gear, and fitness apparel.",
        "logo_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
    },
    {
        "name": "Crossword Bookstore",
        "slug": "crossword-bookstore",
        "description": "India's beloved chain for bestsellers, literary classics, and premium stationery.",
        "logo_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=200&q=80",
        "rating": 4.9,
        "state": "MH",
    },
]

# Statutory Indian GST Tax brackets per product category
# 0% = Books & educational printed material (HSN 4901)
# 5% = Food grains, rice, basic garments (HSN 1006, 6109)
# 12% = Processed dairy/ghee, fitness gear, luxury ethnic wear (HSN 0405, 9506, 6204)
# 18% = Electronics, computing, personal care, furniture (HSN 8518, 8471, 3304, 9403)
CATEGORY_STATUTORY_TAX_MAP: dict[str, tuple[str, int]] = {
    "electronics": ("8518", 1800),
    "fashion": ("6109", 500),
    "groceries": ("1006", 500),
    "beauty": ("3304", 1800),
    "home-furniture": ("9403", 1800),
    "sports-fitness": ("9506", 1200),
    "books-stationery": ("4901", 0),
}

CATEGORIES_DATA = [
    {
        "name": "Electronics",
        "slug": "electronics",
        "description": "Smartphones, laptops, audio gear, and cutting-edge personal computing.",
        "image_url": "https://images.unsplash.com/photo-1498049794561-7780e7231661?auto=format&fit=crop&w=800&q=80",
        "icon": "Laptop",
    },
    {
        "name": "Fashion",
        "slug": "fashion",
        "description": "Contemporary and traditional Indian wear, premium footwear, and accessories.",
        "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80",
        "icon": "Shirt",
    },
    {
        "name": "Groceries",
        "slug": "groceries",
        "description": "Fresh pantry essentials, cold-pressed oils, exotic spices, and organic staples.",
        "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
        "icon": "Apple",
    },
    {
        "name": "Beauty & Wellness",
        "slug": "beauty",
        "description": "Dermatologist-tested skincare, luxury fragrances, and herbal grooming.",
        "image_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        "icon": "Sparkles",
    },
    {
        "name": "Home & Furniture",
        "slug": "home-furniture",
        "description": "Ergonomic seating, handcrafted teak furniture, and modern ambient lighting.",
        "image_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80",
        "icon": "Home",
    },
    {
        "name": "Sports & Fitness",
        "slug": "sports-fitness",
        "description": "Pro-grade exercise equipment, trail running shoes, and yoga accessories.",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
        "icon": "Dumbbell",
    },
    {
        "name": "Books & Stationery",
        "slug": "books-stationery",
        "description": "Award-winning non-fiction, Indian literature, notebooks, and fine writing pens.",
        "image_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=800&q=80",
        "icon": "BookOpen",
    },
]

PRODUCTS_DATA = [
    # 1. Electronics
    {
        "category_slug": "electronics",
        "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "slug": "sony-wh-1000xm5-wireless-headphones",
        "brand": "Sony",
        "description": "Industry-leading active noise cancellation with dual processors, 8 microphones, LDAC Hi-Res audio, and 30-hour battery life with quick charge.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Sony WH-1000XM5 Black front view",
                "is_primary": True,
                "sort_order": 0,
            },
            {
                "url": "https://images.unsplash.com/photo-1484704849700-f032a568e944?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Sony WH-1000XM5 Silver profile view",
                "is_primary": False,
                "sort_order": 1,
            },
        ],
        "variants": [
            {
                "name": "Midnight Black",
                "sku": "SNY-XM5-BLK",
                "attributes": {"color": "Midnight Black"},
                "listings": [
                    {
                        "retailer_slug": "croma",
                        "original_price_paise": 3499000,
                        "selling_price_paise": 2999000,
                        "on_hand": 25,
                        "reserved": 2,
                    },
                    {
                        "retailer_slug": "reliance-digital",
                        "original_price_paise": 3499000,
                        "selling_price_paise": 2899000,
                        "on_hand": 18,
                        "reserved": 0,
                    },
                ],
            },
            {
                "name": "Platinum Silver",
                "sku": "SNY-XM5-SLV",
                "attributes": {"color": "Platinum Silver"},
                "listings": [
                    {
                        "retailer_slug": "croma",
                        "original_price_paise": 3499000,
                        "selling_price_paise": 2999000,
                        "on_hand": 14,
                        "reserved": 1,
                    },
                ],
            },
        ],
    },
    {
        "category_slug": "electronics",
        "name": "Apple MacBook Air 15-inch M3",
        "slug": "apple-macbook-air-15-m3",
        "brand": "Apple",
        "description": "Impossibly thin and fast with the Apple M3 chip, Liquid Retina display, MagSafe 3 charging, and up to 18 hours of battery life.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "MacBook Air 15 open display",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "16GB RAM / 512GB SSD - Space Grey",
                "sku": "APL-MBA15-512-GRY",
                "attributes": {
                    "ram": "16GB",
                    "storage": "512GB",
                    "color": "Space Grey",
                },
                "listings": [
                    {
                        "retailer_slug": "reliance-digital",
                        "original_price_paise": 15490000,
                        "selling_price_paise": 14290000,
                        "on_hand": 10,
                        "reserved": 1,
                    },
                    {
                        "retailer_slug": "croma",
                        "original_price_paise": 15490000,
                        "selling_price_paise": 14490000,
                        "on_hand": 8,
                        "reserved": 0,
                    },
                ],
            },
            {
                "name": "8GB RAM / 256GB SSD - Starlight",
                "sku": "APL-MBA15-256-STR",
                "attributes": {"ram": "8GB", "storage": "256GB", "color": "Starlight"},
                "listings": [
                    {
                        "retailer_slug": "reliance-digital",
                        "original_price_paise": 13490000,
                        "selling_price_paise": 12490000,
                        "on_hand": 15,
                        "reserved": 2,
                    },
                ],
            },
        ],
    },
    # 2. Fashion
    {
        "category_slug": "fashion",
        "name": "FabIndia Pure Tussar Silk Kurta Set",
        "slug": "fabindia-pure-tussar-silk-kurta-set",
        "brand": "FabIndia",
        "description": "Crafted from hand-spun wild Tussar silk featuring delicate contrast kantha stitching along the Mandarin collar and tailored churidar pants.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Handcrafted silk ethnic wear",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "Size 40 (Medium) - Royal Ochre",
                "sku": "FAB-TSK-40-OCH",
                "attributes": {"size": "40 (M)", "color": "Royal Ochre"},
                "listings": [
                    {
                        "retailer_slug": "fabindia",
                        "original_price_paise": 899900,
                        "selling_price_paise": 749900,
                        "on_hand": 20,
                        "reserved": 0,
                    },
                    {
                        "retailer_slug": "tata-cliq",
                        "original_price_paise": 899900,
                        "selling_price_paise": 769900,
                        "on_hand": 12,
                        "reserved": 1,
                    },
                ],
            },
            {
                "name": "Size 42 (Large) - Royal Ochre",
                "sku": "FAB-TSK-42-OCH",
                "attributes": {"size": "42 (L)", "color": "Royal Ochre"},
                "listings": [
                    {
                        "retailer_slug": "fabindia",
                        "original_price_paise": 899900,
                        "selling_price_paise": 749900,
                        "on_hand": 15,
                        "reserved": 0,
                    },
                ],
            },
        ],
    },
    {
        "category_slug": "fashion",
        "name": "Woods Handcrafted Italian Leather Chelsea Boots",
        "slug": "woods-leather-chelsea-boots",
        "brand": "Woods",
        "description": "Full-grain burnished leather upper with Goodyear welt construction, elasticized side gussets, and high-traction Vibram rubber soles.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Handcrafted Italian leather Chelsea boots",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "UK 8 - Tan Brown",
                "sku": "WDS-CHL-08-TAN",
                "attributes": {"size": "UK 8", "color": "Tan Brown"},
                "listings": [
                    {
                        "retailer_slug": "tata-cliq",
                        "original_price_paise": 1199900,
                        "selling_price_paise": 999900,
                        "on_hand": 10,
                        "reserved": 0,
                    },
                ],
            },
            {
                "name": "UK 9 - Tan Brown",
                "sku": "WDS-CHL-09-TAN",
                "attributes": {"size": "UK 9", "color": "Tan Brown"},
                "listings": [
                    {
                        "retailer_slug": "tata-cliq",
                        "original_price_paise": 1199900,
                        "selling_price_paise": 999900,
                        "on_hand": 8,
                        "reserved": 0,
                    },
                ],
            },
        ],
    },
    # 3. Groceries
    {
        "category_slug": "groceries",
        "name": "Organic Kashmir Valley Acacia Honey (500g)",
        "slug": "organic-kashmir-acacia-honey-500g",
        "brand": "Nature's Nectar",
        "description": "Unpasteurized, single-origin raw honey harvested sustainably from wild acacia blossoms in the high-altitude meadows of Kashmir.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Raw golden organic acacia honey jar",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "500g Glass Jar",
                "sku": "NN-HON-500G",
                "attributes": {"weight": "500g", "packaging": "Glass Jar"},
                "listings": [
                    {
                        "retailer_slug": "natures-basket",
                        "original_price_paise": 125000,
                        "selling_price_paise": 99900,
                        "on_hand": 65,
                        "reserved": 3,
                    },
                ],
            },
            {
                "name": "1kg Value Jar",
                "sku": "NN-HON-1KG",
                "attributes": {"weight": "1kg", "packaging": "Glass Jar"},
                "listings": [
                    {
                        "retailer_slug": "natures-basket",
                        "original_price_paise": 220000,
                        "selling_price_paise": 179900,
                        "on_hand": 40,
                        "reserved": 1,
                    },
                ],
            },
        ],
    },
    {
        "category_slug": "groceries",
        "name": "Estate Selection Cold-Pressed Extra Virgin Olive Oil (1L)",
        "slug": "estate-selection-extra-virgin-olive-oil-1l",
        "brand": "Olivares Real",
        "description": "First cold extraction from handpicked olives within 4 hours of harvest. Rich in polyphenols with balanced peppery notes.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Dark glass bottle of extra virgin olive oil",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "1 Litre Dark Bottle",
                "sku": "OLV-EVOO-1L",
                "attributes": {"volume": "1L"},
                "listings": [
                    {
                        "retailer_slug": "natures-basket",
                        "original_price_paise": 195000,
                        "selling_price_paise": 165000,
                        "on_hand": 30,
                        "reserved": 2,
                    },
                ],
            },
        ],
    },
    # 4. Beauty
    {
        "category_slug": "beauty",
        "name": "Forest Essentials Kumkumadi Ayurvedic Night Cream",
        "slug": "forest-essentials-kumkumadi-night-cream",
        "brand": "Forest Essentials",
        "description": "Formulated with pure saffron stamens, sandalwood, and sweet almond oil using traditional Vedic decoction for radiant skin.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Luxury Ayurvedic skincare night cream jar",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "50g Jar",
                "sku": "FE-KUM-50G",
                "attributes": {"volume": "50g"},
                "listings": [
                    {
                        "retailer_slug": "tata-cliq",
                        "original_price_paise": 325000,
                        "selling_price_paise": 289900,
                        "on_hand": 22,
                        "reserved": 0,
                    },
                ],
            },
        ],
    },
    # 5. Home and furniture
    {
        "category_slug": "home-furniture",
        "name": "Featherlite Helix Ergonomic Executive Mesh Chair",
        "slug": "featherlite-helix-ergonomic-chair",
        "brand": "Featherlite",
        "description": "Engineered for 12+ hour seating comfort with 4D adjustable armrests, pneumatic seat height, synchronous tilt-lock, and breathable Korean mesh back.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1505797149-43b0069ec26b?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Ergonomic executive mesh office chair",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "Graphite Grey with Lumbar Support",
                "sku": "FL-HLX-GRY",
                "attributes": {"color": "Graphite Grey", "lumbar": "Adjustable"},
                "listings": [
                    {
                        "retailer_slug": "reliance-digital",
                        "original_price_paise": 2499900,
                        "selling_price_paise": 1999900,
                        "on_hand": 12,
                        "reserved": 1,
                    },
                ],
            },
            {
                "name": "All Black Edition",
                "sku": "FL-HLX-BLK",
                "attributes": {"color": "Jet Black", "lumbar": "Adjustable"},
                "listings": [
                    {
                        "retailer_slug": "reliance-digital",
                        "original_price_paise": 2499900,
                        "selling_price_paise": 1949900,
                        "on_hand": 15,
                        "reserved": 0,
                    },
                ],
            },
        ],
    },
    # 6. Sports and fitness
    {
        "category_slug": "sports-fitness",
        "name": "Decathlon Domyos Hex Dumbbell Set (Pair)",
        "slug": "decathlon-domyos-hex-dumbbell-pair",
        "brand": "Domyos",
        "description": "Commercial rubber coated hexagonal cast-iron dumbbells with knurled ergonomic chrome handles. Anti-roll floor safety design.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Hexagon dumbbells pair in gym",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "7.5 kg Pair",
                "sku": "DEC-HEX-075",
                "attributes": {"weight": "7.5 kg each", "total": "15 kg"},
                "listings": [
                    {
                        "retailer_slug": "decathlon-india",
                        "original_price_paise": 449900,
                        "selling_price_paise": 379900,
                        "on_hand": 28,
                        "reserved": 2,
                    },
                ],
            },
            {
                "name": "12.5 kg Pair",
                "sku": "DEC-HEX-125",
                "attributes": {"weight": "12.5 kg each", "total": "25 kg"},
                "listings": [
                    {
                        "retailer_slug": "decathlon-india",
                        "original_price_paise": 749900,
                        "selling_price_paise": 629900,
                        "on_hand": 16,
                        "reserved": 0,
                    },
                ],
            },
        ],
    },
    # 7. Books and stationery
    {
        "category_slug": "books-stationery",
        "name": "Lamy 2000 Makrolon Fountain Pen (Fine Nib)",
        "slug": "lamy-2000-makrolon-fountain-pen",
        "brand": "Lamy",
        "description": "Timeless Bauhaus masterpiece crafted from fiberglass-reinforced Makrolon polycarbonate and brushed stainless steel with a hand-polished 14K gold platinum-coated nib.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1583485088034-697b5bc54ccd?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Fine fountain pen writing on paper",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "Fine (F) Nib - Matte Black",
                "sku": "LMY-2000-F",
                "attributes": {"nib": "Fine (F)", "material": "Makrolon"},
                "listings": [
                    {
                        "retailer_slug": "crossword-bookstore",
                        "original_price_paise": 2200000,
                        "selling_price_paise": 1899900,
                        "on_hand": 9,
                        "reserved": 0,
                    },
                ],
            },
            {
                "name": "Medium (M) Nib - Matte Black",
                "sku": "LMY-2000-M",
                "attributes": {"nib": "Medium (M)", "material": "Makrolon"},
                "listings": [
                    {
                        "retailer_slug": "crossword-bookstore",
                        "original_price_paise": 2200000,
                        "selling_price_paise": 1899900,
                        "on_hand": 11,
                        "reserved": 1,
                    },
                ],
            },
        ],
    },
    {
        "category_slug": "books-stationery",
        "name": "Sapiens: A Brief History of Humankind (Collector's Hardcover)",
        "slug": "sapiens-a-brief-history-of-humankind",
        "brand": "Vintage Classics",
        "description": "Yuval Noah Harari's groundbreaking global phenomenon exploring how biology and history have defined us and enhanced our understanding of what it means to be human.",
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=1000&q=80",
                "alt_text": "Hardcover book on wooden study desk",
                "is_primary": True,
                "sort_order": 0,
            },
        ],
        "variants": [
            {
                "name": "Collector's Illustrated Hardcover",
                "sku": "SAP-HC-ILL",
                "attributes": {"binding": "Hardcover", "edition": "Illustrated"},
                "listings": [
                    {
                        "retailer_slug": "crossword-bookstore",
                        "original_price_paise": 149900,
                        "selling_price_paise": 109900,
                        "on_hand": 50,
                        "reserved": 3,
                    },
                ],
            },
        ],
    },
]


async def seed_database() -> None:
    """Idempotently seed categories, retailers, products, variants, listings, and inventory."""
    setup_logging()
    logger.info("Starting catalogue database seed operation...")

    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database engine not configured. Cannot seed database.")

    async with session_factory() as session:
        # 1. Seed Retailers
        retailer_map: dict[str, Retailer] = {}
        for r_data in RETAILERS_DATA:
            res = await session.execute(
                select(Retailer).where(Retailer.slug == r_data["slug"])
            )
            retailer = res.scalar_one_or_none()
            if not retailer:
                retailer = Retailer(
                    id=uuid.uuid4(),
                    name=r_data["name"],
                    slug=r_data["slug"],
                    description=r_data["description"],
                    logo_url=r_data["logo_url"],
                    rating=r_data["rating"],
                    state=r_data["state"],
                    state_source="PROVISIONAL_SEED",
                    is_active=True,
                )
                session.add(retailer)
                await session.flush()
                logger.info("Created retailer: %s", retailer.name)
            else:
                if r_data.get("state") and retailer.state != r_data["state"]:
                    retailer.state = r_data["state"]
            retailer_map[retailer.slug] = retailer

        # 2. Seed Categories
        category_map: dict[str, Category] = {}
        for c_data in CATEGORIES_DATA:
            res = await session.execute(
                select(Category).where(Category.slug == c_data["slug"])
            )
            cat = res.scalar_one_or_none()
            if not cat:
                cat = Category(
                    id=uuid.uuid4(),
                    name=c_data["name"],
                    slug=c_data["slug"],
                    description=c_data["description"],
                    image_url=c_data["image_url"],
                    icon=c_data["icon"],
                    is_active=True,
                )
                session.add(cat)
                await session.flush()
                logger.info("Created category: %s", cat.name)
            category_map[cat.slug] = cat

        # 3. Seed Products, Variants, Images, Listings, and Inventory
        for p_data in PRODUCTS_DATA:
            category = category_map[p_data["category_slug"]]
            res = await session.execute(
                select(Product).where(Product.slug == p_data["slug"])
            )
            product = res.scalar_one_or_none()
            if product:
                # Update image URLs for existing product
                img_res = await session.execute(
                    select(ProductImage)
                    .where(ProductImage.product_id == product.id)
                    .order_by(ProductImage.sort_order)
                )
                existing_imgs = list(img_res.scalars().all())
                for idx, img_data in enumerate(p_data.get("images", [])):
                    if idx < len(existing_imgs):
                        existing_imgs[idx].url = img_data["url"]
                        existing_imgs[idx].alt_text = img_data.get("alt_text")
            else:
                product = Product(
                    id=uuid.uuid4(),
                    category_id=category.id,
                    name=p_data["name"],
                    slug=p_data["slug"],
                    brand=p_data["brand"],
                    description=p_data["description"],
                    is_active=True,
                )
                session.add(product)
                await session.flush()
                logger.info("Created product: %s", product.name)

                # Images
                for img_data in p_data.get("images", []):
                    img = ProductImage(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        url=img_data["url"],
                        alt_text=img_data.get("alt_text"),
                        is_primary=img_data.get("is_primary", False),
                        sort_order=img_data.get("sort_order", 0),
                    )
                    session.add(img)

                # Variants
                for v_data in p_data.get("variants", []):
                    variant = ProductVariant(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        name=v_data["name"],
                        sku=v_data["sku"],
                        attributes=v_data.get("attributes", {}),
                        is_active=True,
                    )
                    session.add(variant)
                    await session.flush()

                    # Listings & Inventory
                    for l_data in v_data.get("listings", []):
                        retailer = retailer_map[l_data["retailer_slug"]]
                        default_hsn, default_gst = CATEGORY_STATUTORY_TAX_MAP.get(
                            category.slug, ("8518", 1800)
                        )
                        hsn_code = l_data.get("hsn_code", default_hsn)
                        gst_rate_basis_points = l_data.get(
                            "gst_rate_basis_points", default_gst
                        )
                        listing = ProductListing(
                            id=uuid.uuid4(),
                            retailer_id=retailer.id,
                            variant_id=variant.id,
                            seller_sku=f"{retailer.slug[:3].upper()}-{variant.sku}",
                            original_price_paise=l_data["original_price_paise"],
                            selling_price_paise=l_data["selling_price_paise"],
                            currency="INR",
                            hsn_code=hsn_code,
                            gst_rate_basis_points=gst_rate_basis_points,
                            tax_classification_source="PROVISIONAL_SEED",
                            is_tax_verified=True,
                            is_active=True,
                        )
                        session.add(listing)
                        await session.flush()

                        inv = StoreInventory(
                            id=uuid.uuid4(),
                            listing_id=listing.id,
                            on_hand_quantity=l_data.get("on_hand", 10),
                            reserved_quantity=l_data.get("reserved", 0),
                        )
                        session.add(inv)

        # Synchronize statutory HSN and GST rates across all existing listings
        for cat_slug, (
            statutory_hsn,
            statutory_gst,
        ) in CATEGORY_STATUTORY_TAX_MAP.items():
            cat_obj = category_map.get(cat_slug)
            if cat_obj:
                update_stmt = (
                    select(ProductListing)
                    .join(
                        ProductVariant, ProductListing.variant_id == ProductVariant.id
                    )
                    .join(Product, ProductVariant.product_id == Product.id)
                    .where(Product.category_id == cat_obj.id)
                )
                res_listings = await session.execute(update_stmt)
                for existing_l in res_listings.scalars().all():
                    existing_l.hsn_code = statutory_hsn
                    existing_l.gst_rate_basis_points = statutory_gst
                    existing_l.tax_classification_source = "PROVISIONAL_SEED"
                    existing_l.is_tax_verified = True

        await session.commit()
        logger.info("Catalogue seed operation completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
