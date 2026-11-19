"""
BASKET Marketplace Authenticity & Catalogue Seed Script
Idempotent, deterministic script to:
1. Deactivate legacy test/fake retailers, categories, and dummy products.
2. Maintain max 15 verified active Indian retailers (preserving dev admin and retailer).
3. Populate an authentic multi-category catalogue across 10 categories with realistic INR pricing.
4. Create multi-retailer variant listings with authentic StoreInventory records.
5. Create sample historical confirmed orders to populate retailer sales analytics.
6. Reconcile OpenSearch derived read-model if OpenSearch is available.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import func, select, update

import app.modules.inventory.models  # noqa: F401
import app.modules.payments.models  # noqa: F401
import app.modules.pricing.models  # noqa: F401
from app.core.config import settings
from app.core.database import get_session_factory
from app.core.logging import setup_logging
from app.core.search.client import get_opensearch_client
from app.core.search.index import IndexManager
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.identity.models import User
from app.modules.orders.models import Order, OrderItem, OrderStatus, PaymentStatus

setup_logging()
logger = logging.getLogger("seed_marketplace_data")

UTC = datetime.UTC

# The approved list of active retailers (Max 15)
AUTHENTIC_RETAILERS: list[dict[str, Any]] = [
    {
        "name": "Basket Superstore (Dev Partner)",
        "slug": "basket-superstore-dev",
        "description": "BASKET flagship verified partner store with multi-category premier inventory.",
        "logo_url": "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=200&q=80",
        "rating": 4.9,
        "state": "KA",
        "business_address": "100 Feet Road, Indiranagar, Bengaluru, Karnataka - 560038",
        "contact_phone": "+918041128900",
        "contact_email": "partner.support@basket.local",
    },
    {
        "name": "Bengaluru Tech Store",
        "slug": "bengaluru-tech-store",
        "description": "Premier consumer laptops, Apple workstations, and computing gear.",
        "logo_url": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
        "business_address": "80 Feet Road, HAL 2nd Stage, Bengaluru, Karnataka - 560008",
        "contact_phone": "+918025214455",
        "contact_email": "sales@bengalurutech.in",
    },
    {
        "name": "Metro Electronics Hub",
        "slug": "metro-electronics-hub",
        "description": "High-fidelity audio, smart displays, and modern electronics.",
        "logo_url": "https://images.unsplash.com/photo-1550009158-9ebf69173e03?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "KA",
        "business_address": "Hosur Road, Electronic City Phase 1, Bengaluru, Karnataka - 560100",
        "contact_phone": "+918067119200",
        "contact_email": "support@metroelectronics.in",
    },
    {
        "name": "Premium Mobile Hub",
        "slug": "premium-mobile-hub",
        "description": "Authorized flagship smartphones, tablets, and genuine fast-charging accessories.",
        "logo_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
        "business_address": "MG Road, Shanthala Nagar, Bengaluru, Karnataka - 560001",
        "contact_phone": "+918025583311",
        "contact_email": "contact@premiummobile.in",
    },
    {
        "name": "Smart Appliances India",
        "slug": "smart-appliances-india",
        "description": "Smart washing machines, cordless vacuums, and kitchen appliances.",
        "logo_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=200&q=80",
        "rating": 4.6,
        "state": "KA",
        "business_address": "ITPL Main Road, Whitefield, Bengaluru, Karnataka - 560066",
        "contact_phone": "+918049127700",
        "contact_email": "care@smartappliances.in",
    },
    {
        "name": "Urban Home & Living",
        "slug": "urban-home-living",
        "description": "Kitchen appliances, cookware, and modern interior essentials.",
        "logo_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "KA",
        "business_address": "5th Block, Koramangala, Bengaluru, Karnataka - 560095",
        "contact_phone": "+918041205588",
        "contact_email": "orders@urbanhomeliving.in",
    },
    {
        "name": "Everyday Essentials Mart",
        "slug": "everyday-essentials-mart",
        "description": "Daily pantry staples, premium cooking oils, pulses, and household provisions.",
        "logo_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=200&q=80",
        "rating": 4.9,
        "state": "KA",
        "business_address": "27th Main Road, HSR Layout Sector 1, Bengaluru, Karnataka - 560102",
        "contact_phone": "+918022581122",
        "contact_email": "help@everydayessentials.in",
    },
    {
        "name": "Fresh Basket Organics",
        "slug": "fresh-basket-organics",
        "description": "Certified organic staples, cold-pressed oils, and farm-sourced unpolished grains.",
        "logo_url": "https://images.unsplash.com/photo-1610348725531-843dff563e2c?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
        "business_address": "4th Block, Jayanagar, Bengaluru, Karnataka - 560011",
        "contact_phone": "+918026639900",
        "contact_email": "organics@freshbasket.in",
    },
    {
        "name": "City Fashion House",
        "slug": "city-fashion-house",
        "description": "Contemporary denim, formal suits, branded casuals, and lifestyle footwear.",
        "logo_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=200&q=80",
        "rating": 4.6,
        "state": "KA",
        "business_address": "Commercial Street, Tasker Town, Bengaluru, Karnataka - 560001",
        "contact_phone": "+918025598812",
        "contact_email": "style@cityfashionhouse.in",
    },
    {
        "name": "Active Sports & Fitness",
        "slug": "active-sports-fitness",
        "description": "Professional racquets, training weights, yoga mats, and marathon footwear.",
        "logo_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
        "business_address": "Outer Ring Road, Marathahalli, Bengaluru, Karnataka - 560037",
        "contact_phone": "+918043220011",
        "contact_email": "support@activesports.in",
    },
    {
        "name": "Beauty & Wellness Care",
        "slug": "beauty-wellness-care",
        "description": "Ayurvedic skincare, premium face serums, moisturizers, and personal hygiene.",
        "logo_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "KA",
        "business_address": "Bashyam Circle, Sadashivanagar, Bengaluru, Karnataka - 560080",
        "contact_phone": "+918023617744",
        "contact_email": "care@beautywellness.in",
    },
    {
        "name": "Heritage Book Depot",
        "slug": "heritage-book-depot",
        "description": "Best-selling non-fiction, philosophy, literature, and premium stationery.",
        "logo_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=200&q=80",
        "rating": 4.9,
        "state": "KA",
        "business_address": "Margosa Road, Malleshwaram, Bengaluru, Karnataka - 560003",
        "contact_phone": "+918023346622",
        "contact_email": "books@heritagebooks.in",
    },
    {
        "name": "Office & Study Depot",
        "slug": "office-study-depot",
        "description": "Fine fountain pens, notebooks, organizers, and productivity essentials.",
        "logo_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=200&q=80",
        "rating": 4.7,
        "state": "KA",
        "business_address": "Church Street, Ashok Nagar, Bengaluru, Karnataka - 560001",
        "contact_phone": "+918025554488",
        "contact_email": "supplies@officedepot.in",
    },
    {
        "name": "Artisan Home Decor",
        "slug": "artisan-home-decor",
        "description": "Handcrafted brassware, ceramics, ambient lanterns, and decorative tableware.",
        "logo_url": "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=200&q=80",
        "rating": 4.6,
        "state": "KA",
        "business_address": "Lavelle Road, Shanthala Nagar, Bengaluru, Karnataka - 560001",
        "contact_phone": "+918041132277",
        "contact_email": "decor@artisanhomedecor.in",
    },
    {
        "name": "Royal Indian Spices & Foods",
        "slug": "royal-indian-spices-foods",
        "description": "Traditional aromatic spice blends, whole spices, and Indian condiments.",
        "logo_url": "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?auto=format&fit=crop&w=200&q=80",
        "rating": 4.8,
        "state": "KA",
        "business_address": "BVK Iyengar Road, Chickpet, Bengaluru, Karnataka - 560053",
        "contact_phone": "+918022873399",
        "contact_email": "info@royalindianspices.in",
    },
]

# 10 Canonical Product Categories
AUTHENTIC_CATEGORIES: list[dict[str, Any]] = [
    {
        "slug": "electronics",
        "name": "Electronics",
        "description": "High-fidelity audio, wireless headphones, and consumer smart devices.",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80",
        "icon": "Headphones",
    },
    {
        "slug": "computers-laptops",
        "name": "Computers & Laptops",
        "description": "MacBooks, ultra-portable laptops, workstation hardware, and displays.",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80",
        "icon": "Laptop",
    },
    {
        "slug": "mobiles-accessories",
        "name": "Mobiles & Accessories",
        "description": "Flagship 5G smartphones, fast chargers, and durable phone cases.",
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80",
        "icon": "Smartphone",
    },
    {
        "slug": "home-appliances",
        "name": "Home Appliances",
        "description": "Cordless vacuums, AI washing machines, smart air fryers, and home utilities.",
        "image_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=800&q=80",
        "icon": "WashingMachine",
    },
    {
        "slug": "fashion",
        "name": "Fashion",
        "description": "Branded denim, running footwear, casuals, and formal apparel.",
        "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80",
        "icon": "Shirt",
    },
    {
        "slug": "home-kitchen",
        "name": "Home & Kitchen",
        "description": "Heavy-duty mixer grinders, stainless steel flasks, and cookware.",
        "image_url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=800&q=80",
        "icon": "Home",
    },
    {
        "slug": "groceries",
        "name": "Grocery & Essentials",
        "description": "Pantry staples, premium unpolished pulses, sunflower oil, and rice.",
        "image_url": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
        "icon": "Apple",
    },
    {
        "slug": "beauty",
        "name": "Beauty & Personal Care",
        "description": "Dermatologist-recommended skincare, moisturizers, and facial cleansers.",
        "image_url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        "icon": "Sparkles",
    },
    {
        "slug": "sports-fitness",
        "name": "Sports & Fitness",
        "description": "Pro badminton racquets, training weights, and yoga accessories.",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
        "icon": "Dumbbell",
    },
    {
        "slug": "books-stationery",
        "name": "Books & Stationery",
        "description": "Bestselling books, habit-building classics, notebooks, and fine pens.",
        "image_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=800&q=80",
        "icon": "BookOpen",
    },
]

# Canonical Products with multi-seller offers and realistic INR prices
AUTHENTIC_CATALOGUE = [
    # 1. Computers & Laptops: MacBook Air 15 M3
    {
        "name": "Apple MacBook Air 15-inch M3",
        "slug": "apple-macbook-air-15-m3",
        "brand": "Apple",
        "category_slug": "computers-laptops",
        "description": "The 15-inch MacBook Air is impossibly thin and has a stunning Liquid Retina display. Supercharged by the M3 chip with an 8-core CPU and 10-core GPU, it delivers up to 18 hours of battery life.",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "16GB RAM / 512GB SSD - Midnight",
                "sku": "APL-MBA15-512-MID",
                "attributes": {"color": "Midnight", "ram": "16GB", "storage": "512GB"},
                "offers": [
                    {
                        "retailer_slug": "bengaluru-tech-store",
                        "seller_sku": "BTS-MBA15-MID-512",
                        "mrp_paise": 13490000,
                        "selling_paise": 12490000,  # ₹1,24,900
                        "stock": 25,
                    },
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "BDEV-MBA15-MID-512",
                        "mrp_paise": 13490000,
                        "selling_paise": 12690000,  # ₹1,26,900
                        "stock": 20,
                    },
                    {
                        "retailer_slug": "metro-electronics-hub",
                        "seller_sku": "MEH-MBA15-MID-512",
                        "mrp_paise": 13490000,
                        "selling_paise": 12749000,  # ₹1,27,490
                        "stock": 18,
                    },
                ],
            },
            {
                "name": "16GB RAM / 512GB SSD - Space Grey",
                "sku": "APL-MBA15-512-GRY",
                "attributes": {"color": "Space Grey", "ram": "16GB", "storage": "512GB"},
                "offers": [
                    {
                        "retailer_slug": "bengaluru-tech-store",
                        "seller_sku": "BTS-MBA15-GRY-512",
                        "mrp_paise": 13490000,
                        "selling_paise": 12590000,  # ₹1,25,900
                        "stock": 22,
                    },
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "BDEV-MBA15-GRY-512",
                        "mrp_paise": 13490000,
                        "selling_paise": 12690000,  # ₹1,26,900
                        "stock": 15,
                    },
                ],
            },
        ],
    },
    # 2. Computers & Laptops: MacBook Air 13 M2
    {
        "name": "Apple MacBook Air 13-inch M2",
        "slug": "apple-macbook-air-13-m2",
        "brand": "Apple",
        "category_slug": "computers-laptops",
        "description": "Redesigned around the next-generation M2 chip, MacBook Air is strikingly thin and brings exceptional speed and power efficiency inside its durable all-aluminum enclosure.",
        "image_url": "https://images.unsplash.com/photo-1611186871348-b1ce696e52c9?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "8GB RAM / 256GB SSD - Starlight",
                "sku": "APL-MBA13-256-STL",
                "attributes": {"color": "Starlight", "ram": "8GB", "storage": "256GB"},
                "offers": [
                    {
                        "retailer_slug": "bengaluru-tech-store",
                        "seller_sku": "BTS-MBA13-STL-256",
                        "mrp_paise": 9990000,
                        "selling_paise": 8990000,  # ₹89,900
                        "stock": 30,
                    },
                    {
                        "retailer_slug": "metro-electronics-hub",
                        "seller_sku": "MEH-MBA13-STL-256",
                        "mrp_paise": 9990000,
                        "selling_paise": 9149000,  # ₹91,490
                        "stock": 20,
                    },
                ],
            },
        ],
    },
    # 3. Mobiles: iPhone 15 Pro
    {
        "name": "Apple iPhone 15 Pro",
        "slug": "apple-iphone-15-pro",
        "brand": "Apple",
        "category_slug": "mobiles-accessories",
        "description": "iPhone 15 Pro features a strong and light aerospace-grade titanium design with textured matte-glass back. Powered by the A17 Pro chip and customizable Action button.",
        "image_url": "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "128GB - Natural Titanium",
                "sku": "APL-IP15P-128-NT",
                "attributes": {"color": "Natural Titanium", "storage": "128GB"},
                "offers": [
                    {
                        "retailer_slug": "premium-mobile-hub",
                        "seller_sku": "PMH-IP15P-128-NT",
                        "mrp_paise": 13490000,
                        "selling_paise": 12490000,  # ₹1,24,900
                        "stock": 35,
                    },
                    {
                        "retailer_slug": "bengaluru-tech-store",
                        "seller_sku": "BTS-IP15P-128-NT",
                        "mrp_paise": 13490000,
                        "selling_paise": 12590000,  # ₹1,25,900
                        "stock": 20,
                    },
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "BDEV-IP15P-128-NT",
                        "mrp_paise": 13490000,
                        "selling_paise": 12649000,  # ₹1,26,490
                        "stock": 15,
                    },
                ],
            },
        ],
    },
    # 4. Mobiles: Samsung Galaxy S24 Ultra
    {
        "name": "Samsung Galaxy S24 Ultra 5G",
        "slug": "samsung-galaxy-s24-ultra",
        "brand": "Samsung",
        "category_slug": "mobiles-accessories",
        "description": "Meet Galaxy S24 Ultra, the ultimate form of Galaxy Ultra with a new titanium exterior and a 6.8-inch flat display. Built with Galaxy AI for effortless productivity.",
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "12GB RAM / 256GB - Titanium Gray",
                "sku": "SAM-S24U-256-GRY",
                "attributes": {"color": "Titanium Gray", "ram": "12GB", "storage": "256GB"},
                "offers": [
                    {
                        "retailer_slug": "premium-mobile-hub",
                        "seller_sku": "PMH-S24U-256-GRY",
                        "mrp_paise": 12999900,
                        "selling_paise": 11999900,  # ₹1,19,999
                        "stock": 28,
                    },
                    {
                        "retailer_slug": "metro-electronics-hub",
                        "seller_sku": "MEH-S24U-256-GRY",
                        "mrp_paise": 12999900,
                        "selling_paise": 12149000,  # ₹1,21,490
                        "stock": 15,
                    },
                ],
            },
        ],
    },
    # 5. Electronics: Sony WH-1000XM5
    {
        "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "slug": "sony-wh-1000xm5-wireless-headphones",
        "brand": "Sony",
        "category_slug": "electronics",
        "description": "Industry-leading noise cancellation with two processors and eight microphones. Magnificent sound quality engineered to perfection with 30-hour battery life.",
        "image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "Midnight Black",
                "sku": "SNY-XM5-BLK",
                "attributes": {"color": "Black"},
                "offers": [
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "DEV-SKU-SNY-XM5-BLK-1",
                        "mrp_paise": 3499000,
                        "selling_paise": 2699000,  # ₹26,990
                        "stock": 45,
                    },
                    {
                        "retailer_slug": "metro-electronics-hub",
                        "seller_sku": "MEH-XM5-BLK",
                        "mrp_paise": 3499000,
                        "selling_paise": 2749000,  # ₹27,490
                        "stock": 25,
                    },
                ],
            },
            {
                "name": "Platinum Silver",
                "sku": "SNY-XM5-SLV",
                "attributes": {"color": "Silver"},
                "offers": [
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "DEV-SKU-SNY-XM5-SLV-2",
                        "mrp_paise": 3499000,
                        "selling_paise": 2699000,  # ₹26,990
                        "stock": 35,
                    },
                ],
            },
        ],
    },
    # 5b. Electronics: Apple AirPods Pro (2nd Generation)
    {
        "name": "Apple AirPods Pro (2nd Generation) with MagSafe Case (USB-C)",
        "slug": "apple-airpods-pro-2nd-gen",
        "brand": "Apple",
        "category_slug": "electronics",
        "description": "Up to 2x more Active Noise Cancellation, Transparency mode, and Adaptive Audio. Personalized Spatial Audio with dynamic head tracking for immersive sound.",
        "image_url": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "White with USB-C Case",
                "sku": "APL-APP2-WHT",
                "attributes": {"color": "White", "connectivity": "USB-C"},
                "offers": [
                    {
                        "retailer_slug": "basket-superstore-dev",
                        "seller_sku": "BKT-APP2-WHT",
                        "mrp_paise": 2490000,
                        "selling_paise": 2199000,  # ₹21,990
                        "stock": 35,
                    },
                    {
                        "retailer_slug": "metro-electronics-hub",
                        "seller_sku": "MEH-APP2-WHT",
                        "mrp_paise": 2490000,
                        "selling_paise": 2249000,  # ₹22,490
                        "stock": 25,
                    },
                ],
            },
        ],
    },
    # 6. Home Appliances: Dyson V12 Detect Slim
    {
        "name": "Dyson V12 Detect Slim Cordless Vacuum",
        "slug": "dyson-v12-detect-slim",
        "brand": "Dyson",
        "category_slug": "home-appliances",
        "description": "Dyson's lightest intelligent cordless vacuum with laser illumination that reveals invisible dust on hard floors. Powerful Hyperdymium motor spins up to 125,000rpm.",
        "image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "Standard Nickel / Iron",
                "sku": "DYS-V12-STD",
                "attributes": {"color": "Yellow/Iron"},
                "offers": [
                    {
                        "retailer_slug": "smart-appliances-india",
                        "seller_sku": "SAI-DYS-V12",
                        "mrp_paise": 5590000,
                        "selling_paise": 4790000,  # ₹47,900
                        "stock": 20,
                    },
                    {
                        "retailer_slug": "urban-home-living",
                        "seller_slug": "urban-home-living",
                        "seller_sku": "UHL-DYS-V12",
                        "mrp_paise": 5590000,
                        "selling_paise": 4849000,  # ₹48,490
                        "stock": 14,
                    },
                ],
            },
        ],
    },
    # 7. Home & Kitchen: Prestige Iris Mixer Grinder
    {
        "name": "Prestige Iris 750W Mixer Grinder",
        "slug": "prestige-iris-750w-mixer-grinder",
        "brand": "Prestige",
        "category_slug": "home-kitchen",
        "description": "Prestige Iris 750 Watt mixer grinder with 3 stainless steel multipurpose jars and 1 transparent juicer jar with sharp stainless steel blades for robust kitchen blending.",
        "image_url": "https://images.unsplash.com/photo-1574269909862-7e1d70bb8078?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "750W 4-Jar Set - White/Blue",
                "sku": "PRS-IRIS-750W",
                "attributes": {"power": "750W", "jars": "4"},
                "offers": [
                    {
                        "retailer_slug": "urban-home-living",
                        "seller_sku": "UHL-PRS-IRIS",
                        "mrp_paise": 619500,
                        "selling_paise": 349900,  # ₹3,499
                        "stock": 45,
                    },
                    {
                        "retailer_slug": "smart-appliances-india",
                        "seller_sku": "SAI-PRS-IRIS",
                        "mrp_paise": 619500,
                        "selling_paise": 359900,  # ₹3,599
                        "stock": 30,
                    },
                ],
            },
        ],
    },
    # 8. Fashion: Nike Air Zoom Pegasus 40
    {
        "name": "Nike Air Zoom Pegasus 40 Running Shoes",
        "slug": "nike-air-zoom-pegasus-40",
        "brand": "Nike",
        "category_slug": "fashion",
        "description": "A springy ride for any run, the Peg's familiar, just-for-you feel returns to help you accomplish your goals. Dual Zoom Air units deliver energized toe-offs.",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "UK 9 / US 10 - Black/White",
                "sku": "NKE-PEG40-UK9-BLK",
                "attributes": {"size": "UK 9", "color": "Black/White"},
                "offers": [
                    {
                        "retailer_slug": "city-fashion-house",
                        "seller_sku": "CFH-PEG40-UK9",
                        "mrp_paise": 1149500,
                        "selling_paise": 899500,  # ₹8,995
                        "stock": 35,
                    },
                    {
                        "retailer_slug": "active-sports-fitness",
                        "seller_sku": "ASF-PEG40-UK9",
                        "mrp_paise": 1149500,
                        "selling_paise": 929500,  # ₹9,295
                        "stock": 25,
                    },
                ],
            },
        ],
    },
    # 9. Grocery: Tata Sampann Toor Dal
    {
        "name": "Tata Sampann Unpolished Toor Dal",
        "slug": "tata-sampann-unpolished-toor-dal",
        "brand": "Tata Sampann",
        "category_slug": "groceries",
        "description": "Unpolished Toor Dal does not undergo artificial polishing with water, oil or leather, thereby retaining its wholesome nutrients and authentic taste.",
        "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "1kg Pouch",
                "sku": "TAT-DAL-1KG",
                "attributes": {"weight": "1kg"},
                "offers": [
                    {
                        "retailer_slug": "everyday-essentials-mart",
                        "seller_sku": "EEM-DAL-1KG",
                        "mrp_paise": 21000,
                        "selling_paise": 17500,  # ₹175
                        "stock": 90,
                    },
                    {
                        "retailer_slug": "fresh-basket-organics",
                        "seller_sku": "FBO-DAL-1KG",
                        "mrp_paise": 21000,
                        "selling_paise": 18000,  # ₹180
                        "stock": 70,
                    },
                ],
            },
        ],
    },
    # 10. Books & Stationery: Atomic Habits
    {
        "name": "Atomic Habits by James Clear",
        "slug": "atomic-habits-james-clear",
        "brand": "Random House Business",
        "category_slug": "books-stationery",
        "description": "An Easy & Proven Way to Build Good Habits & Break Bad Ones. Over 15 million copies sold worldwide. Transformative insights into daily compounding.",
        "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=800&q=80",
        "variants": [
            {
                "name": "Paperback Edition",
                "sku": "BK-ATOM-PB",
                "attributes": {"format": "Paperback", "language": "English"},
                "offers": [
                    {
                        "retailer_slug": "heritage-book-depot",
                        "seller_sku": "HBD-ATOM-PB",
                        "mrp_paise": 79900,
                        "selling_paise": 49900,  # ₹499
                        "stock": 60,
                    },
                    {
                        "retailer_slug": "office-study-depot",
                        "seller_sku": "OSD-ATOM-PB",
                        "mrp_paise": 79900,
                        "selling_paise": 52500,  # ₹525
                        "stock": 40,
                    },
                ],
            },
        ],
    },
]


async def seed_marketplace() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        logger.info("Step 1: Soft-deactivating legacy test retailers, categories, and dummy products...")

        # Find dev retailer user
        dev_retailer_user = (
            await session.execute(
                select(User).where(User.email == "retailer.dev@basket.local")
            )
        ).scalar_one_or_none()

        approved_slugs = [r["slug"] for r in AUTHENTIC_RETAILERS]

        # Soft-deactivate any retailer not in our authentic list (preserving IDs for historical orders)
        await session.execute(
            update(Retailer)
            .where(
                Retailer.slug.not_in(approved_slugs),
                Retailer.name != "Basket Superstore (Dev Partner)",
            )
            .values(is_active=False)
        )

        # Soft-deactivate test categories
        await session.execute(
            update(Category)
            .where(
                Category.slug.like("admin-test-%")
                | Category.slug.like("cat-a-%")
                | Category.slug.like("cat-b-%")
                | Category.name.like("Admin Test%")
            )
            .values(is_active=False)
        )

        # Soft-deactivate test products
        await session.execute(
            update(Product)
            .where(Product.name.like("Test Product%"))
            .values(is_active=False)
        )
        await session.flush()

        logger.info("Step 2: Upserting authentic categories...")
        cat_map: dict[str, Category] = {}
        for cat_data in AUTHENTIC_CATEGORIES:
            existing_cat = (
                await session.execute(
                    select(Category).where(Category.slug == cat_data["slug"])
                )
            ).scalar_one_or_none()
            if existing_cat:
                existing_cat.name = cat_data["name"]
                existing_cat.description = cat_data["description"]
                existing_cat.image_url = cat_data["image_url"]
                existing_cat.icon = cat_data["icon"]
                existing_cat.is_active = True
                cat_map[cat_data["slug"]] = existing_cat
            else:
                new_cat = Category(
                    id=uuid.uuid4(),
                    slug=cat_data["slug"],
                    name=cat_data["name"],
                    description=cat_data["description"],
                    image_url=cat_data["image_url"],
                    icon=cat_data["icon"],
                    is_active=True,
                )
                session.add(new_cat)
                cat_map[cat_data["slug"]] = new_cat
        await session.flush()

        logger.info("Step 3: Upserting max 15 verified authentic retailers...")
        ret_map: dict[str, Retailer] = {}
        now = datetime.datetime.now(UTC)

        for r_data in AUTHENTIC_RETAILERS:
            existing_r = (
                await session.execute(
                    select(Retailer).where(
                        (Retailer.slug == r_data["slug"])
                        | (Retailer.name == r_data["name"])
                    )
                )
            ).scalar_one_or_none()

            # If this is the dev partner, ensure it is linked to retailer.dev@basket.local
            user_id = dev_retailer_user.id if (r_data["slug"] == "basket-superstore-dev" and dev_retailer_user) else None

            if existing_r:
                existing_r.name = r_data["name"]
                existing_r.slug = r_data["slug"]
                existing_r.description = r_data["description"]
                existing_r.logo_url = r_data["logo_url"]
                existing_r.rating = r_data["rating"]
                existing_r.state = r_data["state"]
                existing_r.business_address = r_data["business_address"]
                existing_r.contact_phone = r_data["contact_phone"]
                existing_r.contact_email = r_data["contact_email"]
                existing_r.verification_status = "VERIFIED"
                existing_r.is_active = True
                existing_r.is_open = True
                existing_r.verified_at = now
                if user_id and not existing_r.user_id:
                    existing_r.user_id = user_id
                ret_map[r_data["slug"]] = existing_r
            else:
                new_r = Retailer(
                    id=uuid.uuid4(),
                    name=r_data["name"],
                    slug=r_data["slug"],
                    description=r_data["description"],
                    logo_url=r_data["logo_url"],
                    rating=r_data["rating"],
                    state=r_data["state"],
                    business_address=r_data["business_address"],
                    contact_phone=r_data["contact_phone"],
                    contact_email=r_data["contact_email"],
                    verification_status="VERIFIED",
                    is_active=True,
                    is_open=True,
                    verified_at=now,
                    user_id=user_id,
                )
                session.add(new_r)
                ret_map[r_data["slug"]] = new_r
        await session.flush()

        logger.info("Step 4: Upserting authentic products, variants, and retailer offers...")
        seeded_listings: list[ProductListing] = []

        for p_data in AUTHENTIC_CATALOGUE:
            category = cat_map[p_data["category_slug"]]
            product = (
                await session.execute(
                    select(Product).where(Product.slug == p_data["slug"])
                )
            ).scalar_one_or_none()

            if not product:
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

                # Add primary image
                primary_image = ProductImage(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    url=p_data["image_url"],
                    alt_text=p_data["name"],
                    is_primary=True,
                    sort_order=0,
                )
                session.add(primary_image)
            else:
                product.category_id = category.id
                product.name = p_data["name"]
                product.brand = p_data["brand"]
                product.description = p_data["description"]
                product.is_active = True

            await session.flush()

            # Upsert variants
            for v_data in p_data["variants"]:
                variant = (
                    await session.execute(
                        select(ProductVariant).where(
                            ProductVariant.sku == v_data["sku"]
                        )
                    )
                ).scalar_one_or_none()

                if not variant:
                    variant = ProductVariant(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        name=v_data["name"],
                        sku=v_data["sku"],
                        attributes=v_data["attributes"],
                        is_active=True,
                    )
                    session.add(variant)
                    await session.flush()
                else:
                    variant.product_id = product.id
                    variant.name = v_data["name"]
                    variant.attributes = v_data["attributes"]
                    variant.is_active = True
                    await session.flush()

                # Upsert offers for each retailer
                for o_data in v_data["offers"]:
                    retailer = ret_map.get(o_data["retailer_slug"])
                    if not retailer:
                        continue

                    listing = (
                        await session.execute(
                            select(ProductListing).where(
                                ProductListing.retailer_id == retailer.id,
                                ProductListing.variant_id == variant.id,
                            )
                        )
                    ).scalar_one_or_none()

                    if not listing:
                        listing = ProductListing(
                            id=uuid.uuid4(),
                            retailer_id=retailer.id,
                            variant_id=variant.id,
                            seller_sku=o_data["seller_sku"],
                            original_price_paise=o_data["mrp_paise"],
                            selling_price_paise=o_data["selling_paise"],
                            currency="INR",
                            hsn_code="8471",
                            gst_rate_basis_points=1800,
                            is_active=True,
                        )
                        session.add(listing)
                        await session.flush()
                    else:
                        listing.seller_sku = o_data["seller_sku"]
                        listing.original_price_paise = o_data["mrp_paise"]
                        listing.selling_price_paise = o_data["selling_paise"]
                        listing.is_active = True
                        await session.flush()

                    seeded_listings.append(listing)

                    # Ensure StoreInventory exists
                    inventory = (
                        await session.execute(
                            select(StoreInventory).where(
                                StoreInventory.listing_id == listing.id
                            )
                        )
                    ).scalar_one_or_none()

                    if not inventory:
                        inventory = StoreInventory(
                            id=uuid.uuid4(),
                            listing_id=listing.id,
                            on_hand_quantity=o_data["stock"],
                            reserved_quantity=0,
                            low_stock_threshold=5,
                        )
                        session.add(inventory)
                    else:
                        inventory.on_hand_quantity = o_data["stock"]
                        inventory.reserved_quantity = 0
                        inventory.low_stock_threshold = 5

        await session.flush()

        logger.info("Step 5: Seeding sample confirmed historical orders for retailer analytics...")
        # Check if we already have sample orders
        existing_order_count = (
            await session.execute(select(func.count(Order.id)))
        ).scalar() or 0

        # Create orders if less than 5 orders exist
        if existing_order_count < 5 and seeded_listings:
            # Pick a customer user or dev admin
            customer_user = (
                await session.execute(
                    select(User).where(User.role.in_(["customer", "admin"]))
                )
            ).scalars().first()

            if customer_user:
                for idx, listing in enumerate(seeded_listings[:6]):
                    order_id = uuid.uuid4()
                    qty = 1 + (idx % 2)
                    item_price = listing.selling_price_paise
                    subtotal = qty * item_price
                    tax = int(subtotal * 0.18)
                    total = subtotal + tax

                    order = Order(
                        id=order_id,
                        order_number=f"ORD-DEMO-{1001 + idx}",
                        customer_id=customer_user.id,
                        customer_email=customer_user.email,
                        customer_phone=customer_user.phone or "+919876543210",
                        customer_name=customer_user.full_name,
                        status=OrderStatus.CONFIRMED.value,
                        payment_status=PaymentStatus.SUCCEEDED.value,
                        currency="INR",
                        subtotal_paise=subtotal,
                        tax_paise=tax,
                        delivery_fee_paise=0,
                        discount_paise=0,
                        total_paise=total,
                        shipping_address_line1="123 MG Road",
                        shipping_city="Bengaluru",
                        shipping_state="KA",
                        shipping_postal_code="560001",
                        shipping_country="IN",
                        created_at=now - datetime.timedelta(days=idx + 1),
                        confirmed_at=now - datetime.timedelta(days=idx + 1),
                    )
                    session.add(order)
                    await session.flush()

                    # Query variant and product title
                    variant = (
                        await session.execute(
                            select(ProductVariant).where(
                                ProductVariant.id == listing.variant_id
                            )
                        )
                    ).scalar_one()

                    product = (
                        await session.execute(
                            select(Product).where(Product.id == variant.product_id)
                        )
                    ).scalar_one()

                    item = OrderItem(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        listing_id=listing.id,
                        variant_id=listing.variant_id,
                        retailer_id=listing.retailer_id,
                        product_title=product.name,
                        variant_title=variant.name,
                        sku=listing.seller_sku or variant.sku,
                        hsn_code=listing.hsn_code or "8471",
                        gst_rate_basis_points=listing.gst_rate_basis_points or 1800,
                        quantity=qty,
                        unit_original_price_paise=listing.original_price_paise,
                        unit_selling_price_paise=listing.selling_price_paise,
                        unit_discount_paise=max(0, listing.original_price_paise - listing.selling_price_paise),
                    )
                    session.add(item)
                    await session.flush()

        await session.commit()
        logger.info("Database marketplace seeding and cleanup completed successfully.")

    # Step 6: Synchronize OpenSearch index if configured
    if settings.has_opensearch:
        try:
            logger.info("Step 6: Ensuring OpenSearch index and reconciling derived documents...")
            os_client = get_opensearch_client(settings)
            if await os_client.ping():
                idx_mgr = IndexManager(client=os_client)
                await idx_mgr.ensure_index_and_aliases()
                async with session_factory() as session:
                    reconciled_count = await idx_mgr.reconcile_from_database(session)
                    logger.info("OpenSearch reconciled %d products.", reconciled_count)
            else:
                logger.warning("OpenSearch ping failed; skipping search index reconciliation.")
        except Exception as exc:
            logger.warning("OpenSearch reconciliation failed (falling back safely to PostgreSQL): %s", exc)


if __name__ == "__main__":
    asyncio.run(seed_marketplace())
