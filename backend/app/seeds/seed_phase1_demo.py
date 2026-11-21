"""
BASKET — Phase 1 Master Core Marketplace Seed Script
Provisions:
1. Two Demo Retailers:
   - Basket Mart (retailer1@basket.demo / Basket@123)
   - Basket Lifestyle (retailer2@basket.demo / Basket@123)
   Plus dev Admin (admin@basket.demo / Basket@123) and Customer (customer@basket.demo / Basket@123)
2. Exactly 10 Top-Level Categories (parent_id IS NULL)
3. Exactly 50 Realistic Demo Products (25 for Basket Mart, 25 for Basket Lifestyle)
   across all 10 categories (2 or 3 per category per retailer).
4. Realistic pricing, GST, HSN codes, unique SKUs, high-quality images, and StoreInventory.
5. Retailer discounts/offers and sample orders.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import func, select, update

import app.modules.cart.models  # noqa: F401
import app.modules.payments.models  # noqa: F401
from app.core.database import get_session_factory
from app.core.logging import setup_logging
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.identity.models import Address, User
from app.modules.identity.security import hash_password
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
)
from app.modules.pricing.models import (
    CheckoutQuote,
    Discount,
    DiscountType,
    QuoteStatus,
)

setup_logging()
logger = logging.getLogger("seed_phase1_demo")
UTC = datetime.UTC

# 10 Top-Level Categories
TOP_LEVEL_CATEGORIES: list[dict[str, Any]] = [
    {
        "slug": "grocery-food",
        "name": "Grocery & Food",
        "description": "Daily organic groceries, pantry staples, cold-pressed oils, premium dry fruits, and gourmet condiments.",
        "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
        "icon": "Apple",
    },
    {
        "slug": "electronics",
        "name": "Electronics",
        "description": "High-fidelity audio, wireless headphones, laptops, smart accessories, and premium consumer electronics.",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80",
        "icon": "Headphones",
    },
    {
        "slug": "fashion-clothing",
        "name": "Fashion & Clothing",
        "description": "Contemporary men's and women's apparel, denim jeans, classic casuals, hoodies, and athletic footwear.",
        "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80",
        "icon": "Shirt",
    },
    {
        "slug": "home-kitchen",
        "name": "Home & Kitchen",
        "description": "Smart air fryers, heavy-duty mixer grinders, stainless steel flasks, and durable non-stick cookware.",
        "image_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=800&q=80",
        "icon": "Home",
    },
    {
        "slug": "beauty-personal-care",
        "name": "Beauty & Personal Care",
        "description": "Dermatologist-tested skincare serums, broad-spectrum sunscreens, gentle cleansers, and nourishing body care.",
        "image_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        "icon": "Sparkles",
    },
    {
        "slug": "sports-fitness",
        "name": "Sports & Fitness",
        "description": "Dumbbell sets, anti-skid yoga mats, professional cricket gear, match footballs, and resistance bands.",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
        "icon": "Dumbbell",
    },
    {
        "slug": "books-stationery",
        "name": "Books & Stationery",
        "description": "Best-selling self-improvement and fiction books, premium hardcover journals, rollerball pens, and office stationery.",
        "image_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=800&q=80",
        "icon": "BookOpen",
    },
    {
        "slug": "furniture-decor",
        "name": "Furniture & Decor",
        "description": "Ergonomic mesh office chairs, engineered wood coffee tables, ambient study lamps, and stylish 3-seater sofas.",
        "image_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80",
        "icon": "Armchair",
    },
    {
        "slug": "automotive-accessories",
        "name": "Automotive Accessories",
        "description": "Universal car mobile mounts, high-power car vacuum cleaners, smart dash cams, and premium car care wash kits.",
        "image_url": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80",
        "icon": "Car",
    },
    {
        "slug": "toys-baby-products",
        "name": "Toys & Baby Products",
        "description": "Creative building block sets, educational board games, baby skincare hampers, and developmental baby gym mats.",
        "image_url": "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088?auto=format&fit=crop&w=800&q=80",
        "icon": "Smile",
    },
]

# 50 Products: 25 for Basket Mart, 25 for Basket Lifestyle
DEMO_PRODUCTS = [
    # ================= RETAILER 1: BASKET MART (25 products) =================
    # 1. Grocery & Food (3)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "grocery-food",
        "name": "Organic Raw Forest Honey 500g",
        "slug": "organic-raw-forest-honey-500g",
        "brand": "Nature's Nest",
        "description": "100% pure, unprocessed raw multi-floral forest honey harvested from wild Himalayan bee colonies. Rich in natural enzymes, antioxidants, and pollen.",
        "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-GROC-HONEY-500",
        "seller_sku": "BM-HONEY-500",
        "mrp_paise": 49900,
        "selling_paise": 39900,
        "hsn_code": "04090000",
        "gst_rate_basis_points": 500,
        "stock": 45,
        "low_stock_threshold": 10,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "grocery-food",
        "name": "Premium Royal Basmati Rice 5kg",
        "slug": "premium-royal-basmati-rice-5kg",
        "brand": "Royal Grain",
        "description": "Aged for two full years to perfection. Extra-long slender grains that double in length after cooking with an authentic aromatic fragrance.",
        "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-GROC-RICE-5KG",
        "seller_sku": "BM-RICE-5KG",
        "mrp_paise": 85000,
        "selling_paise": 69900,
        "hsn_code": "10063020",
        "gst_rate_basis_points": 0,
        "stock": 60,
        "low_stock_threshold": 15,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "grocery-food",
        "name": "California Whole Raw Almonds 500g",
        "slug": "california-whole-raw-almonds-500g",
        "brand": "NutriPure",
        "description": "Premium hand-selected whole California almonds. High in healthy fats, vitamin E, magnesium, and dietary fibre. Vacuum sealed for maximum crunch.",
        "image_url": "https://images.unsplash.com/photo-1508061253366-f7da158b6d46?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-GROC-ALM-500",
        "seller_sku": "BM-ALMOND-500",
        "mrp_paise": 62000,
        "selling_paise": 49900,
        "hsn_code": "08021200",
        "gst_rate_basis_points": 500,
        "stock": 35,
        "low_stock_threshold": 8,
    },
    # 2. Electronics (3)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "electronics",
        "name": "Sony WH-1000XM5 Wireless Headphones",
        "slug": "sony-wh-1000xm5-wireless-headphones",
        "brand": "Sony",
        "description": "Industry-leading active noise cancellation with dual processors, 8 microphones, LDAC Hi-Res audio, and 30-hour battery life with quick charge.",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1000&q=80",
        "sku": "SNY-XM5-BLK",
        "seller_sku": "BM-SONY-XM5-BLK",
        "mrp_paise": 3499000,
        "selling_paise": 2999000,
        "hsn_code": "85183000",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "electronics",
        "name": "boAt Stone 350 10W Portable Bluetooth Speaker",
        "slug": "boat-stone-350-10w-portable-bluetooth-speaker",
        "brand": "boAt",
        "description": "Immersive 10W stereo sound with deep bass, IPX7 splash resistance, and up to 12 hours of playtime. Features TWS pairing for dual stereo sound.",
        "image_url": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-ELEC-BOAT-SPK",
        "seller_sku": "BM-BOAT-S350",
        "mrp_paise": 349000,
        "selling_paise": 149900,
        "hsn_code": "85182200",
        "gst_rate_basis_points": 1800,
        "stock": 4,  # Low stock item
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "electronics",
        "name": "Anker PowerCore 20000mAh Ultra-Compact Power Bank",
        "slug": "anker-powercore-20000mah-ultra-compact-power-bank",
        "brand": "Anker",
        "description": "High-capacity portable battery pack with 20W PowerIQ fast charging. Dual USB-C and USB-A outputs capable of charging smartphones up to 4 times.",
        "image_url": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-ELEC-ANK-20K",
        "seller_sku": "BM-ANKER-20K",
        "mrp_paise": 399900,
        "selling_paise": 249900,
        "hsn_code": "85044090",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 6,
    },
    # 3. Fashion & Clothing (2)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "fashion-clothing",
        "name": "Men's Classic Pure Combed Cotton Crewneck T-Shirt",
        "slug": "mens-classic-pure-combed-cotton-crewneck-tshirt",
        "brand": "CottonCraft",
        "description": "100% bio-washed combed organic cotton 180 GSM t-shirt. Breathable, pre-shrunk fabric with reinforced stitching for supreme all-day comfort.",
        "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-FASH-M-TSHIRT",
        "seller_sku": "BM-CC-TSHIRT-NVY",
        "mrp_paise": 99900,
        "selling_paise": 49900,
        "hsn_code": "61091000",
        "gst_rate_basis_points": 500,
        "stock": 50,
        "low_stock_threshold": 10,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "fashion-clothing",
        "name": "Women's High-Waist Comfort Stretch Denim Jeans",
        "slug": "womens-high-waist-comfort-stretch-denim-jeans",
        "brand": "UrbanDenim",
        "description": "Classic ankle-length slim fit high-rise blue denim jeans crafted with cotton-elastane blend. Contours naturally with five functional pockets.",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-FASH-W-JEANS",
        "seller_sku": "BM-UD-JEANS-BLU",
        "mrp_paise": 249900,
        "selling_paise": 139900,
        "hsn_code": "62046200",
        "gst_rate_basis_points": 1200,
        "stock": 30,
        "low_stock_threshold": 8,
    },
    # 4. Home & Kitchen (3)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "home-kitchen",
        "name": "Philips Digital Air Fryer 4.1L with RapidAir",
        "slug": "philips-digital-air-fryer-4-1l-with-rapidair",
        "brand": "Philips",
        "description": "Bake, grill, roast, and fry with up to 90% less fat. Patented RapidAir starfish design circulates hot air for crispy, even results without oil.",
        "image_url": "https://images.unsplash.com/photo-1584992236310-6edddc08acff?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-HOME-PHIL-AF",
        "seller_sku": "BM-PHIL-AF41",
        "mrp_paise": 999500,
        "selling_paise": 699900,
        "hsn_code": "85167920",
        "gst_rate_basis_points": 1800,
        "stock": 14,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "home-kitchen",
        "name": "Prestige Iris 750W Mixer Grinder with 4 Jars",
        "slug": "prestige-iris-750w-mixer-grinder-with-4-jars",
        "brand": "Prestige",
        "description": "Powerful 750-watt heavy-duty copper motor with 3 stainless steel multipurpose jars and 1 transparent juicer jar with sharp stainless blades.",
        "image_url": "https://images.unsplash.com/photo-1570222094114-d054a817e56b?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-HOME-PREST-MG",
        "seller_sku": "BM-PREST-IRIS750",
        "mrp_paise": 619500,
        "selling_paise": 329900,
        "hsn_code": "85094010",
        "gst_rate_basis_points": 1800,
        "stock": 20,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "home-kitchen",
        "name": "Pigeon Stainless Steel Electric Kettle 1.5L",
        "slug": "pigeon-stainless-steel-electric-kettle-1-5l",
        "brand": "Pigeon",
        "description": "Rapid boil 1500W electric cordless kettle with 360-degree swivel base, auto shut-off, and boil-dry protection. Food-grade hygienic steel body.",
        "image_url": "https://images.unsplash.com/photo-1544717302-de2939b7ef71?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-HOME-PIG-KET",
        "seller_sku": "BM-PIG-KETTLE",
        "mrp_paise": 129500,
        "selling_paise": 64900,
        "hsn_code": "85167990",
        "gst_rate_basis_points": 1800,
        "stock": 0,  # Out of stock item
        "low_stock_threshold": 6,
    },
    # 5. Beauty & Personal Care (3)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "beauty-personal-care",
        "name": "Minimalist 10% Vitamin C Face Serum 30ml",
        "slug": "minimalist-10-vitamin-c-face-serum-30ml",
        "brand": "Minimalist",
        "description": "Clinically proven glow-boosting facial serum formulated with stable Ethyl Ascorbic Acid and Centella Water to fade dark spots and even tone.",
        "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BEAU-VITC-30",
        "seller_sku": "BM-MIN-VITC30",
        "mrp_paise": 69900,
        "selling_paise": 59900,
        "hsn_code": "33049910",
        "gst_rate_basis_points": 1800,
        "stock": 40,
        "low_stock_threshold": 8,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "beauty-personal-care",
        "name": "Neutrogena Ultra Sheer Dry-Touch SPF 50+ Sunscreen 88ml",
        "slug": "neutrogena-ultra-sheer-dry-touch-spf-50-sunscreen-88ml",
        "brand": "Neutrogena",
        "description": "Broad-spectrum UVA/UVB Helioplex technology. Lightweight, oil-free, non-comedogenic matte finish that leaves zero white cast.",
        "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BEAU-NEUT-SUN",
        "seller_sku": "BM-NEUT-SUN88",
        "mrp_paise": 85000,
        "selling_paise": 68000,
        "hsn_code": "33049990",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "beauty-personal-care",
        "name": "Cetaphil Gentle Skin Hydrating Cleanser 250ml",
        "slug": "cetaphil-gentle-skin-hydrating-cleanser-250ml",
        "brand": "Cetaphil",
        "description": "Soap-free, fragrance-free gentle face wash recommended by dermatologists for dry to sensitive skin. Enriched with Niacinamide and Vitamin B5.",
        "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BEAU-CET-CLN",
        "seller_sku": "BM-CET-CLN250",
        "mrp_paise": 62500,
        "selling_paise": 52500,
        "hsn_code": "33049910",
        "gst_rate_basis_points": 1800,
        "stock": 2,  # Low stock item
        "low_stock_threshold": 5,
    },
    # 6. Sports & Fitness (2)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "sports-fitness",
        "name": "Kore PVC 20kg Adjustable Home Dumbbell Kit",
        "slug": "kore-pvc-20kg-adjustable-home-dumbbell-kit",
        "brand": "Kore",
        "description": "Complete strength training combo including 20kg weights (2kg x 4, 3kg x 4), two dumbbell rods with threaded safety locks, and gym gloves.",
        "image_url": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-SPRT-DUMB-20",
        "seller_sku": "BM-KORE-DUMB20",
        "mrp_paise": 249900,
        "selling_paise": 129900,
        "hsn_code": "95069190",
        "gst_rate_basis_points": 1200,
        "stock": 15,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "sports-fitness",
        "name": "Boldfit High Density 6mm Anti-Skid Yoga Mat",
        "slug": "boldfit-high-density-6mm-anti-skid-yoga-mat",
        "brand": "Boldfit",
        "description": "Eco-friendly premium TPE material with dual-sided textured grip for superior traction during yoga, pilates, and floor workout routines. Includes carry strap.",
        "image_url": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-SPRT-YOGA-MAT",
        "seller_sku": "BM-BOLD-YOGA",
        "mrp_paise": 149900,
        "selling_paise": 79900,
        "hsn_code": "95069110",
        "gst_rate_basis_points": 1200,
        "stock": 28,
        "low_stock_threshold": 6,
    },
    # 7. Books & Stationery (3)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "books-stationery",
        "name": "Classmate Pulse A5 Spiral Notebook 300 Pages Pack of 3",
        "slug": "classmate-pulse-a5-spiral-notebook-300-pages-pack-of-3",
        "brand": "Classmate",
        "description": "Elemental chlorine-free bright paper notebooks with durable poly covers and spiral wire binding. Perfect for students and everyday office note taking.",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BOOK-NOTE-A5",
        "seller_sku": "BM-CLASS-A5P3",
        "mrp_paise": 45000,
        "selling_paise": 36000,
        "hsn_code": "48201090",
        "gst_rate_basis_points": 1200,
        "stock": 50,
        "low_stock_threshold": 12,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "books-stationery",
        "name": "Parker Vector Camouflage Rollerball Pen with Refill",
        "slug": "parker-vector-camouflage-rollerball-pen-with-refill",
        "brand": "Parker",
        "description": "Iconic arrow clip design with military matte camouflage finish and stainless steel chrome trim. Smudge-proof Quinkflow liquid rollerball ink.",
        "image_url": "https://images.unsplash.com/photo-1583485088034-697b5bc54ccd?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BOOK-PARK-PEN",
        "seller_sku": "BM-PARK-VECT",
        "mrp_paise": 42500,
        "selling_paise": 37500,
        "hsn_code": "96081019",
        "gst_rate_basis_points": 1800,
        "stock": 30,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "books-stationery",
        "name": "Atomic Habits by James Clear (Paperback)",
        "slug": "atomic-habits-by-james-clear-paperback",
        "brand": "Random House",
        "description": "An easy and proven way to build good habits and break bad ones. The definitive worldwide bestseller by behavioral scientist James Clear.",
        "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-BOOK-ATOM-HAB",
        "seller_sku": "BM-BOOK-ATOM",
        "mrp_paise": 79900,
        "selling_paise": 49900,
        "hsn_code": "49011010",
        "gst_rate_basis_points": 0,
        "stock": 70,
        "low_stock_threshold": 15,
    },
    # 8. Furniture & Decor (2)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "furniture-decor",
        "name": "Green Soul Tokyo Ergonomic High-Back Mesh Office Chair",
        "slug": "green-soul-tokyo-ergonomic-high-back-mesh-office-chair",
        "brand": "Green Soul",
        "description": "Breathable high-density mesh with 2D adjustable lumbar support, 3D armrests, heavy-duty metallic wheelbase, and synchro-tilt mechanism.",
        "image_url": "https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-FURN-GS-CHAIR",
        "seller_sku": "BM-GSOUL-TOKYO",
        "mrp_paise": 1199000,
        "selling_paise": 699900,
        "hsn_code": "94013000",
        "gst_rate_basis_points": 1800,
        "stock": 10,
        "low_stock_threshold": 3,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "furniture-decor",
        "name": "Wudore Engineered Wood Solid Minimalist Coffee Table",
        "slug": "wudore-engineered-wood-solid-minimalist-coffee-table",
        "brand": "Wudore",
        "description": "Modern walnut-finish wooden center table with open storage shelf for magazines and remotes. Termite and moisture resistant finish.",
        "image_url": "https://images.unsplash.com/photo-1533090161767-e6ffed986c88?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-FURN-COFF-TBL",
        "seller_sku": "BM-WUD-COFFEE",
        "mrp_paise": 399900,
        "selling_paise": 199900,
        "hsn_code": "94036000",
        "gst_rate_basis_points": 1800,
        "stock": 12,
        "low_stock_threshold": 3,
    },
    # 9. Automotive Accessories (2)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "automotive-accessories",
        "name": "Portronics CLAMP X Universal Car Mobile Holder Mount",
        "slug": "portronics-clamp-x-universal-car-mobile-holder-mount",
        "brand": "Portronics",
        "description": "360-degree rotation dashboard and windshield phone holder with gel suction cup and one-touch release arms. Compatible with all smartphones up to 6.8 inches.",
        "image_url": "https://images.unsplash.com/photo-1584438784894-089d6a62b8fa?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-AUTO-PORT-HLD",
        "seller_sku": "BM-PORT-CLAMPX",
        "mrp_paise": 99900,
        "selling_paise": 44900,
        "hsn_code": "87082900",
        "gst_rate_basis_points": 1800,
        "stock": 35,
        "low_stock_threshold": 8,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "automotive-accessories",
        "name": "Bergmann Typhoon Heavy Duty High-Power Car Vacuum Cleaner",
        "slug": "bergmann-typhoon-heavy-duty-high-power-car-vacuum-cleaner",
        "brand": "Bergmann",
        "description": "150W 100% pure copper motor with 5.5 kPa strong suction, HEPA filter, 5-meter power cable, and 4 specialized detailing nozzles.",
        "image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-AUTO-BERG-VAC",
        "seller_sku": "BM-BERG-TYPHOON",
        "mrp_paise": 249900,
        "selling_paise": 149900,
        "hsn_code": "85081100",
        "gst_rate_basis_points": 1800,
        "stock": 20,
        "low_stock_threshold": 5,
    },
    # 10. Toys & Baby Products (2)
    {
        "retailer_slug": "basket-mart",
        "category_slug": "toys-baby-products",
        "name": "LEGO Classic Medium Creative Brick Box 10696",
        "slug": "lego-classic-medium-creative-brick-box-10696",
        "brand": "LEGO",
        "description": "484 pieces in 35 different vibrant colours including wheels, windows, and eyes. Designed to encourage open-ended building fun for children aged 4 and above.",
        "image_url": "https://images.unsplash.com/photo-1585366119957-e9730b6d0f60?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-TOYS-LEGO-MED",
        "seller_sku": "BM-LEGO-10696",
        "mrp_paise": 349900,
        "selling_paise": 279900,
        "hsn_code": "95030090",
        "gst_rate_basis_points": 1800,
        "stock": 16,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-mart",
        "category_slug": "toys-baby-products",
        "name": "Himalaya Happy Baby Care Deluxe Gift Basket Pack",
        "slug": "himalaya-happy-baby-care-deluxe-gift-basket-pack",
        "brand": "Himalaya",
        "description": "Gentle baby massage oil, soothing baby lotion, tear-free shampoo, diaper rash cream, and gentle baby wipes. Clinically tested pure ayurvedic formulation.",
        "image_url": "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?auto=format&fit=crop&w=800&q=80",
        "sku": "BM-TOYS-HIM-BABY",
        "seller_sku": "BM-HIM-BABYKIT",
        "mrp_paise": 89900,
        "selling_paise": 74900,
        "hsn_code": "33079090",
        "gst_rate_basis_points": 1200,
        "stock": 22,
        "low_stock_threshold": 5,
    },
    # ================= RETAILER 2: BASKET LIFESTYLE (25 products) =================
    # 1. Grocery & Food (2)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "grocery-food",
        "name": "Borges Extra Virgin Cold Pressed Olive Oil 1 Litre",
        "slug": "borges-extra-virgin-cold-pressed-olive-oil-1-litre",
        "brand": "Borges",
        "description": "Crafted by cold extraction from the finest Spanish Mediterranean olives. Delicate aroma and rich fruitiness ideal for salads, dressings, and dips.",
        "image_url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-GROC-BORG-OIL",
        "seller_sku": "BL-BORG-EVOO1L",
        "mrp_paise": 145000,
        "selling_paise": 109900,
        "hsn_code": "15091000",
        "gst_rate_basis_points": 500,
        "stock": 30,
        "low_stock_threshold": 6,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "grocery-food",
        "name": "Pintola All-Natural Creamy Peanut Butter 1kg",
        "slug": "pintola-all-natural-creamy-peanut-butter-1kg",
        "brand": "Pintola",
        "description": "Made with 100% roasted bold peanuts. Zero added sugar, zero salt, zero hydrogenated oils. 30g high protein per 100g serving.",
        "image_url": "https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-GROC-PINT-PB",
        "seller_sku": "BL-PINT-PB1KG",
        "mrp_paise": 52500,
        "selling_paise": 42500,
        "hsn_code": "20081100",
        "gst_rate_basis_points": 1200,
        "stock": 40,
        "low_stock_threshold": 8,
    },
    # 2. Electronics (3)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "electronics",
        "name": "Apple MacBook Air 13.6-inch M3 Chip 16GB 256GB Midnight",
        "slug": "apple-macbook-air-13-6-inch-m3-chip-16gb-256gb-midnight",
        "brand": "Apple",
        "description": "Blazing-fast M3 chip with 8-core CPU and 10-core GPU, stunning Liquid Retina display, MagSafe 3 charging, and 18-hour battery life.",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-ELEC-MAC-M3",
        "seller_sku": "BL-APL-MBA13-MID",
        "mrp_paise": 11490000,
        "selling_paise": 10490000,
        "hsn_code": "84713010",
        "gst_rate_basis_points": 1800,
        "stock": 12,
        "low_stock_threshold": 3,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "electronics",
        "name": "Samsung Galaxy S24 5G 256GB Onyx Black",
        "slug": "samsung-galaxy-s24-5g-256gb-onyx-black",
        "brand": "Samsung",
        "description": "Equipped with Galaxy AI, Circle to Search, 50MP ProVisual camera engine, and brilliant 6.2-inch FHD+ Dynamic AMOLED 2X display.",
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-ELEC-SAMS-S24",
        "seller_sku": "BL-SAMS-S24-BLK",
        "mrp_paise": 7999900,
        "selling_paise": 6499900,
        "hsn_code": "85171300",
        "gst_rate_basis_points": 1800,
        "stock": 15,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "electronics",
        "name": "Dell Inspiron 15 Core i5 16GB RAM 512GB SSD Laptop",
        "slug": "dell-inspiron-15-core-i5-16gb-ram-512gb-ssd-laptop",
        "brand": "Dell",
        "description": "Intel Core i5 13th Gen processor, 15.6-inch FHD 120Hz anti-glare display, backlit keyboard, Windows 11 Home and MS Office Home 2021.",
        "image_url": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-ELEC-DELL-I15",
        "seller_sku": "BL-DELL-I15-SLV",
        "mrp_paise": 6899000,
        "selling_paise": 5499000,
        "hsn_code": "84713010",
        "gst_rate_basis_points": 1800,
        "stock": 3,  # Low stock item
        "low_stock_threshold": 4,
    },
    # 3. Fashion & Clothing (3)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "fashion-clothing",
        "name": "Allen Solly Men's Slim Fit Casual Oxford Cotton Shirt",
        "slug": "allen-solly-mens-slim-fit-casual-oxford-cotton-shirt",
        "brand": "Allen Solly",
        "description": "Timeless solid Oxford weave woven from long-staple cotton fibers. Features button-down collar, curved hemline, and embroidered stag insignia.",
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FASH-M-SHIRT",
        "seller_sku": "BL-AS-SHIRT-WHT",
        "mrp_paise": 229900,
        "selling_paise": 149900,
        "hsn_code": "62052000",
        "gst_rate_basis_points": 1200,
        "stock": 30,
        "low_stock_threshold": 6,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "fashion-clothing",
        "name": "Puma Unisex Adult Smashic Lightweight Running Sneakers",
        "slug": "puma-unisex-adult-smashic-lightweight-running-sneakers",
        "brand": "Puma",
        "description": "SoftFoam+ sockliner provides superior cushioning and optimal step-in comfort. Durable synthetic leather upper with iconic Puma Formstrip.",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FASH-PUM-SNEAK",
        "seller_sku": "BL-PUMA-SMASH-WHT",
        "mrp_paise": 449900,
        "selling_paise": 229900,
        "hsn_code": "64029990",
        "gst_rate_basis_points": 1800,
        "stock": 20,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "fashion-clothing",
        "name": "Levi's Women's Regular Fit Cotton Pullover Hoodie",
        "slug": "levis-womens-regular-fit-cotton-pullover-hoodie",
        "brand": "Levi's",
        "description": "Ultra-soft brushed fleece inner lining with kangaroo front pocket, ribbed cuffs, and iconic embroidered Batwing logo on chest.",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FASH-LEV-HOOD",
        "seller_sku": "BL-LEV-HOOD-GRY",
        "mrp_paise": 329900,
        "selling_paise": 199900,
        "hsn_code": "61102000",
        "gst_rate_basis_points": 1200,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    # 4. Home & Kitchen (2)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "home-kitchen",
        "name": "Milton Thermosteel Flip Lid Insulated Flask 1000ml",
        "slug": "milton-thermosteel-flip-lid-insulated-flask-1000ml",
        "brand": "Milton",
        "description": "Double-walled vacuum insulated flask keeping beverages hot or cold for up to 24 hours. 100% rust-proof grade 304 stainless steel with carry pouch.",
        "image_url": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-HOME-MIL-FLSK",
        "seller_sku": "BL-MIL-FLASK1L",
        "mrp_paise": 116000,
        "selling_paise": 89900,
        "hsn_code": "96170011",
        "gst_rate_basis_points": 1800,
        "stock": 35,
        "low_stock_threshold": 8,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "home-kitchen",
        "name": "Pigeon by Stovekraft Non-Stick 3-Piece Cookware Set",
        "slug": "pigeon-by-stovekraft-non-stick-3-piece-cookware-set",
        "brand": "Pigeon",
        "description": "5-layer Greblon non-stick German coating. Set includes 240mm Kadai with glass lid, 240mm Fry Pan, and 250mm Flat Dosa Tawa.",
        "image_url": "https://images.unsplash.com/photo-1544982503-9f984c14501a?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-HOME-PIG-COOK",
        "seller_sku": "BL-PIG-COOK3PC",
        "mrp_paise": 289500,
        "selling_paise": 139900,
        "hsn_code": "76151012",
        "gst_rate_basis_points": 1800,
        "stock": 18,
        "low_stock_threshold": 4,
    },
    # 5. Beauty & Personal Care (3)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "beauty-personal-care",
        "name": "L'Oreal Paris Extraordinary Clay Purifying Shampoo 650ml",
        "slug": "loreal-paris-extraordinary-clay-purifying-shampoo-650ml",
        "brand": "L'Oreal Paris",
        "description": "Infused with 3 refined clays to absorb excess oil from roots while deeply hydrating lengths for 72 hours of pure, fresh, bouncy hair.",
        "image_url": "https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-BEAU-LOR-SHMP",
        "seller_sku": "BL-LOR-SHAMP650",
        "mrp_paise": 69900,
        "selling_paise": 54900,
        "hsn_code": "33051090",
        "gst_rate_basis_points": 1800,
        "stock": 35,
        "low_stock_threshold": 7,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "beauty-personal-care",
        "name": "Nivea Nourishing Body Milk 400ml for Very Dry Skin",
        "slug": "nivea-nourishing-body-milk-400ml-for-very-dry-skin",
        "brand": "Nivea",
        "description": "Enriched with 2x almond oil and deep moisture serum to visibly reduce roughness and provide 48-hour intense nourishing hydration.",
        "image_url": "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-BEAU-NIV-LOTN",
        "seller_sku": "BL-NIV-LOTN400",
        "mrp_paise": 49900,
        "selling_paise": 36900,
        "hsn_code": "33049930",
        "gst_rate_basis_points": 1800,
        "stock": 0,  # Out of stock item
        "low_stock_threshold": 6,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "beauty-personal-care",
        "name": "Forest Essentials Pure Rosewater Facial Mist Toner 130ml",
        "slug": "forest-essentials-pure-rosewater-facial-mist-toner-130ml",
        "brand": "Forest Essentials",
        "description": "Steam distilled from fresh Rosa Damascena rose petals harvested in Kannauj. Naturally hydrates, tones, and minimizes enlarged pores.",
        "image_url": "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-BEAU-FE-MIST",
        "seller_sku": "BL-FE-ROSEMIST",
        "mrp_paise": 147500,
        "selling_paise": 135000,
        "hsn_code": "33030090",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    # 6. Sports & Fitness (3)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "sports-fitness",
        "name": "Nivia Storm Football Size 5 Moulded Rubber Ball",
        "slug": "nivia-storm-football-size-5-moulded-rubber-ball",
        "brand": "Nivia",
        "description": "Rubberized 32-panel stitched ball designed for hard outdoor surfaces, artificial turf, and wet conditions. High-air retention butyl bladder.",
        "image_url": "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-SPRT-NIV-BALL",
        "seller_sku": "BL-NIV-STORM5",
        "mrp_paise": 79900,
        "selling_paise": 49900,
        "hsn_code": "95066210",
        "gst_rate_basis_points": 1200,
        "stock": 40,
        "low_stock_threshold": 10,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "sports-fitness",
        "name": "SG Club Kashmir Willow Full Size Adult Cricket Bat",
        "slug": "sg-club-kashmir-willow-full-size-adult-cricket-bat",
        "brand": "SG",
        "description": "Traditional profile with thick edges and curved blade for powerful shot making. Singapore cane handle with special 3-way rubber insertion.",
        "image_url": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-SPRT-SG-CBAT",
        "seller_sku": "BL-SG-CLUBBAT",
        "mrp_paise": 299900,
        "selling_paise": 199900,
        "hsn_code": "95069920",
        "gst_rate_basis_points": 1200,
        "stock": 14,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "sports-fitness",
        "name": "Strauss Power Latex Resistance Exercise Loop Bands Set",
        "slug": "strauss-power-latex-resistance-exercise-loop-bands-set",
        "brand": "Strauss",
        "description": "Set of 5 color-coded 100% natural latex loop bands ranging from X-Light (5 lbs) to X-Heavy (40 lbs). Includes carry bag and workout guide.",
        "image_url": "https://images.unsplash.com/photo-1598289431512-b97b0917affc?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-SPRT-STR-BAND",
        "seller_sku": "BL-STR-BANDS5",
        "mrp_paise": 89900,
        "selling_paise": 44900,
        "hsn_code": "95069190",
        "gst_rate_basis_points": 1200,
        "stock": 35,
        "low_stock_threshold": 8,
    },
    # 7. Books & Stationery (2)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "books-stationery",
        "name": "Moleskine Classic Hardcover Ruled Large Notebook Black",
        "slug": "moleskine-classic-hardcover-ruled-large-notebook-black",
        "brand": "Moleskine",
        "description": "Legendary Italian notebook with rounded corners, ribbon bookmark, elastic closure, and expandable inner rear pocket. 70 GSM acid-free ivory pages.",
        "image_url": "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-BOOK-MOLE-NOTE",
        "seller_sku": "BL-MOLE-LG-BLK",
        "mrp_paise": 249900,
        "selling_paise": 199900,
        "hsn_code": "48201090",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "books-stationery",
        "name": "Pilot V7 Hi-Tecpoint 0.7mm Liquid Ink Roller Pen Pack of 4",
        "slug": "pilot-v7-hi-tecpoint-0-7mm-liquid-ink-roller-pen-pack-of-4",
        "brand": "Pilot",
        "description": "Unique multi-dimple tip system delivers precise skip-free writing. Pure liquid ink controller guarantees consistent ink flow until the last drop.",
        "image_url": "https://images.unsplash.com/photo-1583485088034-697b5bc54ccd?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-BOOK-PIL-V7",
        "seller_sku": "BL-PIL-V7-P4",
        "mrp_paise": 36000,
        "selling_paise": 32000,
        "hsn_code": "96081019",
        "gst_rate_basis_points": 1800,
        "stock": 45,
        "low_stock_threshold": 10,
    },
    # 8. Furniture & Decor (3)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "furniture-decor",
        "name": "IKEA Modern Bedside LED Nordic Night Desk Lamp",
        "slug": "ikea-modern-bedside-led-nordic-night-desk-lamp",
        "brand": "IKEA",
        "description": "Minimalist Scandinavian design with natural solid wood base and soft warm diffused light. Features touch-dimming control with 3 brightness tiers.",
        "image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FURN-IKEA-LAMP",
        "seller_sku": "BL-IKEA-LAMP",
        "mrp_paise": 199900,
        "selling_paise": 129900,
        "hsn_code": "94052090",
        "gst_rate_basis_points": 1800,
        "stock": 18,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "furniture-decor",
        "name": "Solimo Multi-Shelf Engineered Wood Storage Cabinet",
        "slug": "solimo-multi-shelf-engineered-wood-storage-cabinet",
        "brand": "Solimo",
        "description": "4-tier modular multi-utility cupboard with lockable doors. High quality European standard particle board resistant to humidity and warping.",
        "image_url": "https://images.unsplash.com/photo-1595428774223-ef52624120d2?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FURN-SOL-CAB",
        "seller_sku": "BL-SOL-CAB4T",
        "mrp_paise": 899900,
        "selling_paise": 549900,
        "hsn_code": "94036000",
        "gst_rate_basis_points": 1800,
        "stock": 8,
        "low_stock_threshold": 2,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "furniture-decor",
        "name": "Wakefit 3-Seater Fabric Sofa in Charcoal Grey",
        "slug": "wakefit-3-seater-fabric-sofa-in-charcoal-grey",
        "brand": "Wakefit",
        "description": "High-resilience foam cushioning with kiln-dried solid Neem wood frame and breathable anti-pilling premium fabric upholstery.",
        "image_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-FURN-WAK-SOFA",
        "seller_sku": "BL-WAK-SOFA3S",
        "mrp_paise": 2499900,
        "selling_paise": 1599900,
        "hsn_code": "94016100",
        "gst_rate_basis_points": 1800,
        "stock": 6,
        "low_stock_threshold": 2,
    },
    # 9. Automotive Accessories (2)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "automotive-accessories",
        "name": "70mai Smart Dash Cam 1080P Full HD Night Vision",
        "slug": "70mai-smart-dash-cam-1080p-full-hd-night-vision",
        "brand": "70mai",
        "description": "Sony IMX307 sensor with 130-degree wide angle FOV, G-Sensor automatic emergency recording, and integrated Wi-Fi app connectivity.",
        "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-AUTO-70M-DASH",
        "seller_sku": "BL-70MAI-DASH",
        "mrp_paise": 499900,
        "selling_paise": 369900,
        "hsn_code": "85258900",
        "gst_rate_basis_points": 1800,
        "stock": 15,
        "low_stock_threshold": 4,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "automotive-accessories",
        "name": "Wavex High-Gloss All-in-One Car Care Wash & Wax Detailing Kit",
        "slug": "wavex-high-gloss-all-in-one-car-care-wash-wax-detailing-kit",
        "brand": "Wavex",
        "description": "Includes car shampoo with Brazilian Carnauba wax, dashboard polish, tyre shine gel, and two 400 GSM microfibre drying towels.",
        "image_url": "https://images.unsplash.com/photo-1607860108855-64acf2078ed9?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-AUTO-WAV-KIT",
        "seller_sku": "BL-WAVEX-CARE",
        "mrp_paise": 189900,
        "selling_paise": 119900,
        "hsn_code": "34053000",
        "gst_rate_basis_points": 1800,
        "stock": 25,
        "low_stock_threshold": 5,
    },
    # 10. Toys & Baby Products (2)
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "toys-baby-products",
        "name": "Skillmatics Educational Board Game Guess in 10 Animals",
        "slug": "skillmatics-educational-board-game-guess-in-10-animals",
        "brand": "Skillmatics",
        "description": "Smart strategy guessing card game for families and kids aged 6+. Ask up to 10 questions to guess the animal on the game card.",
        "image_url": "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-TOYS-SKIL-GAME",
        "seller_sku": "BL-SKIL-GUESS10",
        "mrp_paise": 59900,
        "selling_paise": 44900,
        "hsn_code": "95049090",
        "gst_rate_basis_points": 1200,
        "stock": 30,
        "low_stock_threshold": 6,
    },
    {
        "retailer_slug": "basket-lifestyle",
        "category_slug": "toys-baby-products",
        "name": "Fisher-Price Kick & Play Deluxe Piano Baby Gym Mat",
        "slug": "fisher-price-kick-play-deluxe-piano-baby-gym-mat",
        "brand": "Fisher-Price",
        "description": "Interactive play mat with 4 musical ways to play as baby grows: Lay & play, Tummy time, Sit & play, and Take along. Includes 5 activity toys.",
        "image_url": "https://images.unsplash.com/photo-1596461404969-9ae70f2830c1?auto=format&fit=crop&w=800&q=80",
        "sku": "BL-TOYS-FISH-GYM",
        "seller_sku": "BL-FISH-PIANO",
        "mrp_paise": 399900,
        "selling_paise": 289900,
        "hsn_code": "95030030",
        "gst_rate_basis_points": 1800,
        "stock": 14,
        "low_stock_threshold": 3,
    },
]


async def seed_phase1_demo() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        logger.info("=== STEP 1: PROVISION AUTHENTICATION & DEMO ACCOUNTS ===")
        # 1. Retailer 1: Basket Mart
        # 2. Retailer 2: Basket Lifestyle
        # 3. Admin: admin@basket.demo
        # 4. Customer: customer@basket.demo
        accounts = [
            {
                "email": "retailer1@basket.demo",
                "role": "retailer",
                "full_name": "Basket Mart Merchant Desk",
                "phone": "+919845011223",
                "store_name": "Basket Mart",
                "store_slug": "basket-mart",
                "description": "Your trusted neighbourhood destination for groceries, household essentials, personal care, and daily lifestyle items.",
                "business_address": "Shop 12-14, Commercial Plaza, Indiranagar 100ft Road, Bengaluru, Karnataka - 560038",
                "contact_phone": "+919845011223",
                "contact_email": "retailer1@basket.demo",
                "logo_url": "https://images.unsplash.com/photo-1534723452862-4c874018d66d?auto=format&fit=crop&w=200&q=80",
            },
            {
                "email": "retailer2@basket.demo",
                "role": "retailer",
                "full_name": "Basket Lifestyle Concierge",
                "phone": "+919845044556",
                "store_name": "Basket Lifestyle",
                "store_slug": "basket-lifestyle",
                "description": "Premier modern lifestyle retailer offering premium electronics, fashion, home decor, sports gear, and automotive accessories.",
                "business_address": "Plot 88, Cyber Gateway Enclave, Whitefield Main Road, Bengaluru, Karnataka - 560066",
                "contact_phone": "+919845044556",
                "contact_email": "retailer2@basket.demo",
                "logo_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=200&q=80",
            },
            {
                "email": "admin@basket.demo",
                "role": "admin",
                "full_name": "Platform Administrator",
                "phone": "+919800000001",
            },
            {
                "email": "customer@basket.demo",
                "role": "customer",
                "full_name": "Rahul Sharma",
                "phone": "+919800000002",
            },
        ]

        created_users: dict[str, User] = {}
        created_retailers: dict[str, Retailer] = {}

        for acc in accounts:
            stmt = select(User).where(User.email == acc["email"])
            user = (await session.execute(stmt)).scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=acc["email"],
                    full_name=acc["full_name"],
                    phone=acc.get("phone"),
                    hashed_password=hash_password("Basket@123"),
                    role=acc["role"],
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                logger.info(f"Created demo account {acc['email']} ({acc['role']})")
            else:
                user.role = acc["role"]
                user.is_active = True
                user.hashed_password = hash_password("Basket@123")
                await session.flush()
            created_users[acc["email"]] = user

            # Create or update linked Retailer entity if role is retailer
            if acc["role"] == "retailer":
                ret_stmt = select(Retailer).where(Retailer.slug == acc["store_slug"])
                retailer = (await session.execute(ret_stmt)).scalar_one_or_none()
                if not retailer:
                    retailer = Retailer(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        name=acc["store_name"],
                        slug=acc["store_slug"],
                        description=acc["description"],
                        business_address=acc["business_address"],
                        contact_phone=acc["contact_phone"],
                        contact_email=acc["contact_email"],
                        logo_url=acc["logo_url"],
                        state="KA",
                        verification_status="VERIFIED",
                        is_active=True,
                        is_open=True,
                        rating=4.9,
                    )
                    session.add(retailer)
                    await session.flush()
                    logger.info(
                        f"Created Retailer entity {acc['store_name']} ({retailer.id})"
                    )
                else:
                    retailer.user_id = user.id
                    retailer.name = acc["store_name"]
                    retailer.description = acc["description"]
                    retailer.business_address = acc["business_address"]
                    retailer.contact_phone = acc["contact_phone"]
                    retailer.contact_email = acc["contact_email"]
                    retailer.logo_url = acc["logo_url"]
                    retailer.verification_status = "VERIFIED"
                    retailer.is_active = True
                    retailer.is_open = True
                    await session.flush()
                created_retailers[acc["store_slug"]] = retailer

        # Ensure customer has a default delivery address
        cust_user = created_users["customer@basket.demo"]
        addr_stmt = select(Address).where(Address.user_id == cust_user.id)
        existing_addr = (await session.execute(addr_stmt)).scalars().first()
        if not existing_addr:
            cust_addr = Address(
                id=uuid.uuid4(),
                user_id=cust_user.id,
                recipient_name="Rahul Sharma",
                phone="+919800000002",
                line1="Apartment 402, Green Glen Heights",
                line2="Bellandur Outer Ring Road",
                landmark="Near Ecospace Tech Park",
                city="Bengaluru",
                state="Karnataka",
                postal_code="560103",
                is_default=True,
            )
            session.add(cust_addr)
            await session.flush()

        logger.info("=== STEP 2: PROVISION EXACTLY 10 TOP-LEVEL CATEGORIES ===")
        # Map slugs to category objects
        category_map: dict[str, Category] = {}
        for cdata in TOP_LEVEL_CATEGORIES:
            cstmt = select(Category).where(Category.slug == cdata["slug"])
            cat = (await session.execute(cstmt)).scalar_one_or_none()
            if not cat:
                cat = Category(
                    id=uuid.uuid4(),
                    name=cdata["name"],
                    slug=cdata["slug"],
                    description=cdata["description"],
                    parent_id=None,
                )
                session.add(cat)
                await session.flush()
                logger.info(f"Created Category: {cdata['name']} ({cdata['slug']})")
            else:
                cat.name = cdata["name"]
                cat.description = cdata["description"]
                cat.parent_id = None
                await session.flush()
            category_map[cdata["slug"]] = cat

        # Clean up or nest any extraneous top-level categories from automated tests so parent_id is not null
        all_top_cats = (
            (
                await session.execute(
                    select(Category).where(
                        Category.parent_id.is_(None),
                        Category.slug.notin_([c["slug"] for c in TOP_LEVEL_CATEGORIES]),
                    )
                )
            )
            .scalars()
            .all()
        )
        for extraneous in all_top_cats:
            # Reassign to Electronics or delete if no products attached
            pcount = (
                await session.execute(
                    select(func.count(Product.id)).where(
                        Product.category_id == extraneous.id
                    )
                )
            ).scalar() or 0
            if pcount == 0:
                await session.delete(extraneous)
            else:
                # Nest under Electronics as subcategory
                extraneous.parent_id = category_map["electronics"].id
        await session.flush()

        logger.info("=== STEP 3: PROVISION EXACTLY 50 REALISTIC DEMO PRODUCTS ===")
        # Deactivate all legacy demo products not in this 50 list to preserve clean counts
        demo_skus = [p["sku"] for p in DEMO_PRODUCTS] + ["SNY-XM5-SLV"]
        demo_slugs = [p["slug"] for p in DEMO_PRODUCTS]
        demo_seller_skus = [p["seller_sku"] for p in DEMO_PRODUCTS]

        await session.execute(
            update(Product)
            .where(Product.slug.notin_(demo_slugs))
            .values(is_active=False)
        )
        await session.execute(
            update(ProductVariant)
            .where(ProductVariant.sku.notin_(demo_skus))
            .values(is_active=False)
        )
        await session.execute(
            update(ProductListing)
            .where(
                ProductListing.retailer_id.in_(
                    [
                        created_retailers["basket-mart"].id,
                        created_retailers["basket-lifestyle"].id,
                    ]
                ),
                ProductListing.seller_sku.notin_(demo_seller_skus),
            )
            .values(is_active=False)
        )
        await session.flush()

        for pdata in DEMO_PRODUCTS:
            ret = created_retailers[pdata["retailer_slug"]]
            cat = category_map[pdata["category_slug"]]

            # Check or create canonical Product
            prod_stmt = select(Product).where(Product.slug == pdata["slug"])
            product = (await session.execute(prod_stmt)).scalar_one_or_none()
            if not product:
                product = Product(
                    id=uuid.uuid4(),
                    name=pdata["name"],
                    slug=pdata["slug"],
                    brand=pdata["brand"],
                    category_id=cat.id,
                    description=pdata["description"],
                    is_active=True,
                )
                session.add(product)
                await session.flush()
            else:
                product.name = pdata["name"]
                product.brand = pdata["brand"]
                product.category_id = cat.id
                product.description = pdata["description"]
                product.is_active = True
                await session.flush()

            # Product Image
            img_stmt = select(ProductImage).where(ProductImage.product_id == product.id)
            img = (await session.execute(img_stmt)).scalars().first()
            if not img:
                img = ProductImage(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    url=pdata["image_url"],
                    is_primary=True,
                    sort_order=0,
                )
                session.add(img)
                await session.flush()
            else:
                img.url = pdata["image_url"]
                img.is_primary = True
                await session.flush()

            # Product Variant
            var_stmt = select(ProductVariant).where(ProductVariant.sku == pdata["sku"])
            variant = (await session.execute(var_stmt)).scalar_one_or_none()
            if not variant:
                variant = ProductVariant(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    name=pdata["name"],
                    sku=pdata["sku"],
                    attributes={"brand": pdata["brand"], "retailer": ret.name},
                    is_active=True,
                )
                session.add(variant)
                await session.flush()
            else:
                variant.product_id = product.id
                variant.name = pdata["name"]
                variant.is_active = True
                await session.flush()

            # Retailer Listing
            list_stmt = select(ProductListing).where(
                ProductListing.retailer_id == ret.id,
                ProductListing.variant_id == variant.id,
            )
            listing = (await session.execute(list_stmt)).scalar_one_or_none()
            if not listing:
                listing = ProductListing(
                    id=uuid.uuid4(),
                    retailer_id=ret.id,
                    variant_id=variant.id,
                    seller_sku=pdata["seller_sku"],
                    original_price_paise=pdata["mrp_paise"],
                    selling_price_paise=pdata["selling_paise"],
                    currency="INR",
                    hsn_code=pdata["hsn_code"],
                    gst_rate_basis_points=pdata["gst_rate_basis_points"],
                    is_active=True,
                )
                session.add(listing)
                await session.flush()
            else:
                listing.seller_sku = pdata["seller_sku"]
                listing.original_price_paise = pdata["mrp_paise"]
                listing.selling_price_paise = pdata["selling_paise"]
                listing.hsn_code = pdata["hsn_code"]
                listing.gst_rate_basis_points = pdata["gst_rate_basis_points"]
                listing.is_active = True
                await session.flush()

            # Store Inventory
            inv_stmt = select(StoreInventory).where(
                StoreInventory.listing_id == listing.id
            )
            inv = (await session.execute(inv_stmt)).scalar_one_or_none()
            if not inv:
                inv = StoreInventory(
                    id=uuid.uuid4(),
                    listing_id=listing.id,
                    on_hand_quantity=pdata["stock"],
                    reserved_quantity=0,
                    low_stock_threshold=pdata["low_stock_threshold"],
                )
                session.add(inv)
                await session.flush()
            else:
                inv.on_hand_quantity = pdata["stock"]
                inv.reserved_quantity = 0
                inv.low_stock_threshold = pdata["low_stock_threshold"]
                await session.flush()

            if pdata["slug"] == "sony-wh-1000xm5-wireless-headphones":
                slv_stmt = select(ProductVariant).where(
                    ProductVariant.sku == "SNY-XM5-SLV"
                )
                slv_var = (await session.execute(slv_stmt)).scalar_one_or_none()
                if not slv_var:
                    slv_var = ProductVariant(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        name="Sony WH-1000XM5 Wireless Headphones (Platinum Silver)",
                        sku="SNY-XM5-SLV",
                        attributes={"brand": "Sony", "color": "Platinum Silver"},
                        is_active=True,
                    )
                    session.add(slv_var)
                    await session.flush()
                else:
                    slv_var.product_id = product.id
                    slv_var.is_active = True
                    await session.flush()

        logger.info("=== STEP 4: PROVISION RETAILER OFFERS & DISCOUNTS ===")
        bm_ret = created_retailers["basket-mart"]
        bl_ret = created_retailers["basket-lifestyle"]

        # Offer 1 for Basket Mart
        bm_offer_code = "MART10"
        bm_offer_stmt = select(Discount).where(Discount.code == bm_offer_code)
        bm_offer = (await session.execute(bm_offer_stmt)).scalar_one_or_none()
        if not bm_offer:
            bm_offer = Discount(
                id=uuid.uuid4(),
                code=bm_offer_code,
                name="Basket Mart Daily Super Saver 10% Off",
                description="Get 10% instant discount on grocery and home kitchen essentials at Basket Mart.",
                discount_type=DiscountType.PERCENTAGE.value,
                discount_value=1000,  # 10.00%
                scope=f"RET_{bm_ret.id.hex[:24]}",
                min_order_paise=50000,  # Min ₹500
                max_discount_paise=15000,  # Max ₹150
                is_active=True,
                valid_from=datetime.datetime.now(UTC),
                valid_to=datetime.datetime.now(UTC) + datetime.timedelta(days=90),
            )
            session.add(bm_offer)
            await session.flush()

        # Offer 2 for Basket Lifestyle
        bl_offer_code = "LIFE15"
        bl_offer_stmt = select(Discount).where(Discount.code == bl_offer_code)
        bl_offer = (await session.execute(bl_offer_stmt)).scalar_one_or_none()
        if not bl_offer:
            bl_offer = Discount(
                id=uuid.uuid4(),
                code=bl_offer_code,
                name="Basket Lifestyle Modern Living 15% Off",
                description="Save 15% on premium electronics and fashion items across Basket Lifestyle.",
                discount_type=DiscountType.PERCENTAGE.value,
                discount_value=1500,  # 15.00%
                scope=f"RET_{bl_ret.id.hex[:24]}",
                min_order_paise=100000,  # Min ₹1000
                max_discount_paise=30000,  # Max ₹300
                is_active=True,
                valid_from=datetime.datetime.now(UTC),
                valid_to=datetime.datetime.now(UTC) + datetime.timedelta(days=90),
            )
            session.add(bl_offer)
            await session.flush()

        logger.info("=== STEP 5: PROVISION SAMPLE ORDERS FOR RETAILERS & CUSTOMER ===")
        # Create a sample multi-retailer order if none exists for customer@basket.demo
        order_check = await session.execute(
            select(Order).where(Order.customer_id == cust_user.id)
        )
        if not order_check.scalars().first():
            # Pick one listing from Mart and one from Lifestyle
            mart_list_stmt = (
                select(ProductListing)
                .where(
                    ProductListing.retailer_id == bm_ret.id,
                    ProductListing.is_active.is_(True),
                )
                .limit(1)
            )
            mart_listing = (await session.execute(mart_list_stmt)).scalar_one()

            life_list_stmt = (
                select(ProductListing)
                .where(
                    ProductListing.retailer_id == bl_ret.id,
                    ProductListing.is_active.is_(True),
                )
                .limit(1)
            )
            life_listing = (await session.execute(life_list_stmt)).scalar_one()

            # Load variants
            mv = (
                await session.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == mart_listing.variant_id
                    )
                )
            ).scalar_one()
            lv = (
                await session.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == life_listing.variant_id
                    )
                )
            ).scalar_one()

            quote_id = uuid.uuid4()
            reservation_id = uuid.uuid4()

            quote = CheckoutQuote(
                id=quote_id,
                customer_id=cust_user.id,
                delivery_address_id=cust_addr.id,
                subtotal_paise=mart_listing.selling_price_paise
                + life_listing.selling_price_paise,
                discount_total_paise=0,
                delivery_fee_paise=4900,
                cgst_paise=int(
                    (
                        mart_listing.selling_price_paise
                        + life_listing.selling_price_paise
                    )
                    * 0.09
                ),
                sgst_paise=int(
                    (
                        mart_listing.selling_price_paise
                        + life_listing.selling_price_paise
                    )
                    * 0.09
                ),
                igst_paise=0,
                total_tax_paise=int(
                    (
                        mart_listing.selling_price_paise
                        + life_listing.selling_price_paise
                    )
                    * 0.18
                ),
                total_payable_paise=(
                    mart_listing.selling_price_paise
                    + life_listing.selling_price_paise
                    + 4900
                    + int(
                        (
                            mart_listing.selling_price_paise
                            + life_listing.selling_price_paise
                        )
                        * 0.18
                    )
                ),
                status=QuoteStatus.CONSUMED.value,
                is_consumed=True,
                expires_at=datetime.datetime.now(UTC) + datetime.timedelta(hours=2),
            )
            session.add(quote)
            await session.flush()

            # Dummy reservation
            res = InventoryReservation(
                id=reservation_id,
                customer_id=cust_user.id,
                quote_id=quote_id,
                status=ReservationStatus.ACTIVE.value,
                expires_at=datetime.datetime.now(UTC) + datetime.timedelta(hours=2),
            )
            session.add(res)
            await session.flush()

            order_id = uuid.uuid4()
            order_num = f"ORD-DEMO-{uuid.uuid4().hex[:6].upper()}"
            address_snap = {
                "recipient_name": cust_addr.recipient_name,
                "phone": cust_addr.phone,
                "line1": cust_addr.line1,
                "line2": cust_addr.line2,
                "city": cust_addr.city,
                "state": cust_addr.state,
                "postal_code": cust_addr.postal_code,
            }

            order = Order(
                id=order_id,
                order_number=order_num,
                customer_id=cust_user.id,
                quote_id=quote_id,
                reservation_id=reservation_id,
                delivery_address_snapshot=address_snap,
                subtotal_paise=quote.subtotal_paise,
                discount_total_paise=0,
                delivery_fee_paise=quote.delivery_fee_paise,
                cgst_paise=quote.cgst_paise,
                sgst_paise=quote.sgst_paise,
                igst_paise=0,
                total_tax_paise=quote.total_tax_paise,
                total_payable_paise=quote.total_payable_paise,
                currency="INR",
                status=OrderStatus.CONFIRMED.value,
                payment_status=PaymentStatus.SUCCEEDED.value,
                payment_window_expires_at=datetime.datetime.now(UTC)
                + datetime.timedelta(hours=1),
            )
            session.add(order)
            await session.flush()

            # Item 1 for Mart
            item1 = OrderItem(
                id=uuid.uuid4(),
                order_id=order_id,
                listing_id=mart_listing.id,
                variant_id=mart_listing.variant_id,
                retailer_id=bm_ret.id,
                product_title=mv.name,
                variant_title=mv.name,
                sku=mv.sku,
                hsn_code=mart_listing.hsn_code or "84713010",
                gst_rate_basis_points=mart_listing.gst_rate_basis_points,
                quantity=1,
                unit_original_price_paise=mart_listing.original_price_paise,
                unit_selling_price_paise=mart_listing.selling_price_paise,
                unit_discount_paise=0,
                unit_discounted_price_paise=mart_listing.selling_price_paise,
                total_selling_price_paise=mart_listing.selling_price_paise,
                taxable_base_paise=mart_listing.selling_price_paise,
                cgst_paise=int(mart_listing.selling_price_paise * 0.09),
                sgst_paise=int(mart_listing.selling_price_paise * 0.09),
                igst_paise=0,
                total_tax_paise=int(mart_listing.selling_price_paise * 0.18),
                retailer_name=bm_ret.name,
                retailer_state="KA",
                fulfillment_status=OrderStatus.CONFIRMED.value,
            )
            session.add(item1)

            # Item 2 for Lifestyle
            item2 = OrderItem(
                id=uuid.uuid4(),
                order_id=order_id,
                listing_id=life_listing.id,
                variant_id=life_listing.variant_id,
                retailer_id=bl_ret.id,
                product_title=lv.name,
                variant_title=lv.name,
                sku=lv.sku,
                hsn_code=life_listing.hsn_code or "84713010",
                gst_rate_basis_points=life_listing.gst_rate_basis_points,
                quantity=1,
                unit_original_price_paise=life_listing.original_price_paise,
                unit_selling_price_paise=life_listing.selling_price_paise,
                unit_discount_paise=0,
                unit_discounted_price_paise=life_listing.selling_price_paise,
                total_selling_price_paise=life_listing.selling_price_paise,
                taxable_base_paise=life_listing.selling_price_paise,
                cgst_paise=int(life_listing.selling_price_paise * 0.09),
                sgst_paise=int(life_listing.selling_price_paise * 0.09),
                igst_paise=0,
                total_tax_paise=int(life_listing.selling_price_paise * 0.18),
                retailer_name=bl_ret.name,
                retailer_state="KA",
                fulfillment_status=OrderStatus.CONFIRMED.value,
            )
            session.add(item2)

            # Status history
            hist = OrderStatusHistory(
                id=uuid.uuid4(),
                order_id=order_id,
                from_status=OrderStatus.PENDING_PAYMENT.value,
                to_status=OrderStatus.CONFIRMED.value,
                reason="Order placed and payment confirmed during seed initialization.",
            )
            session.add(hist)
            await session.flush()
            logger.info(
                f"Created sample confirmed order {order_num} for customer {cust_user.email}"
            )

        await session.commit()
        logger.info("=== PHASE 1 DEMO SEED COMPLETED SUCCESSFULLY ===")

    # Synchronize OpenSearch index with the 50 canonical demo products
    try:
        from app.core.config import settings
        from app.core.search.client import get_opensearch_client
        from app.core.search.index import IndexManager

        os_client = get_opensearch_client(settings)
        if await os_client.ping():
            idx_mgr = IndexManager(client=os_client)
            await idx_mgr.ensure_index_and_aliases()
            async with session_factory() as session:
                synced = await idx_mgr.reconcile_from_database(session)
                logger.info("OpenSearch synchronized %d demo products.", synced)
    except Exception as exc:
        logger.warning(
            "OpenSearch synchronization during seed skipped or failed: %s", exc
        )


if __name__ == "__main__":
    asyncio.run(seed_phase1_demo())
