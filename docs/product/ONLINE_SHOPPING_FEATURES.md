# Online Shopping Platform — Finalized Feature Specification

## Overview

The platform is organized into three distinct roles:
1. **Admin** — manages and controls the marketplace and platform-wide operations.
2. **Retailer** — manages their own store, listings, pricing, inventory, offers, orders, and participation in marketplace demand.
3. **Customer / Purchaser** — discovers and purchases products, manages shopping missions, and uses customer-facing intelligence features.

Each role must have its own dashboard, navigation, workflows, and permissions. Features must only be visible to the role that is authorized to use them. Backend APIs must enforce role-based access control (RBAC); hiding UI elements alone is not sufficient.

---

# 1. Admin Panel

The Admin is the platform controller and manages marketplace-wide products, retailers, customers, deals, demand systems, transactions, analytics, and platform configuration.

## 1.1 Product Management
- Add new products to the platform catalogue.
- Edit product details.
- Delete, deactivate, or archive products.
- Manage product categories and subcategories.
- Add product specifications and attributes.
- Upload and manage product images.
- Manage brands.
- Assign product tags.
- Manage product variants such as size, color, storage, and other attributes.

## 1.2 Platform Deals and Promotions
- Create platform-wide discounts.
- Create special deals and flash sales.
- Create limited-time offers.
- Create seasonal and festival sales.
- Create coupon codes.
- Create product-specific offers.
- Create category-specific offers.
- Create retailer-specific promotional campaigns.
- Configure offer start and expiry dates.
- Set discount limits and eligibility rules.
- Manage promotional banners.

## 1.3 Retailer Management
- Approve or reject retailer registrations.
- Verify retailer documents.
- Suspend or activate retailers.
- View retailer performance.
- Manage retailer permissions.
- Monitor retailer listings and offers.
- Handle retailer disputes.

## 1.4 Customer Management
- View registered customers.
- Manage customer accounts.
- Handle customer complaints.
- Manage account restrictions where applicable.
- Monitor order activity.
- Manage customer support cases.

## 1.5 Demand Intelligence Management
- View aggregated product demand.
- View Demand Gap requests.
- Identify products with unmet demand.
- View demand trends.
- Manage demand thresholds.
- Monitor community-buying groups.
- Send aggregated demand to retailers.
- View demand-based purchasing opportunities.

## 1.6 Dukaan vs Dukaan Management
- Manage retailer competition workflows.
- Configure bidding or offer processes.
- Monitor competing retailer offers.
- Manage request-for-quotation processes.
- Review vendor responses.
- Resolve disputes.

## 1.7 Tax and Pricing Configuration
- Configure platform tax rules.
- Configure applicable GST settings.
- Manage tax categories.
- Configure pricing policies.
- Manage platform commissions.
- Manage service fees.
- Configure shipping-fee rules.
- Review retailer pricing compliance.

## 1.8 Order and Transaction Management
- View all orders.
- Monitor transactions.
- Handle cancellations.
- Handle refunds.
- Manage disputes.
- Monitor order fulfillment.
- View transaction reports.

## 1.9 Analytics and Reports
- Total sales.
- Revenue.
- Number of customers.
- Number of retailers.
- Product performance.
- Category performance.
- Demand analytics.
- Discount performance.
- Order analytics.
- Conversion analytics.
- Marketplace growth.

## 1.10 Platform Configuration
- Manage homepage content.
- Manage featured products.
- Manage categories.
- Manage banners.
- Manage announcements.
- Configure platform settings.
- Manage permissions.
- Manage system-wide policies.

---

# 2. Retailer Panel

Retailers receive a dedicated seller dashboard. They can manage their own store, listings, inventory, pricing, offers, orders, and business performance. Retailers must not have platform-wide administrative privileges.

## 2.1 Store Management
- Create and manage retailer profiles.
- Set store name.
- Upload store logo.
- Add store description.
- Upload store images.
- Set business address.
- Manage contact information.
- Set business hours.
- Configure store policies.
- Set store status (Open / Closed).

## 2.2 Product Listings
- Add products to their store.
- Select products from the platform's existing catalogue.
- Create retailer-specific listings.
- Upload product images.
- Upload additional product images.
- Add product descriptions.
- Add specifications.
- Add product variants.
- Set stock quantity.
- Set SKU.
- Set availability.
- Manage listing status.

## 2.3 Product Pricing
- Set selling price.
- Set MRP.
- Set discounted price.
- Set product-specific pricing.
- Set variant-specific prices.
- Configure bulk pricing.
- Configure quantity-based discounts.
- Set minimum order quantity where applicable.

## 2.4 Retailer Offers and Discounts
- Create retailer-specific offers.
- Create product discounts.
- Create category discounts.
- Create store-wide sales.
- Create coupon codes.
- Create quantity-based offers.
- Create bundle offers.
- Configure offer duration.
- Configure offer limits.
- Schedule upcoming offers.
- Manage active and expired offers.

## 2.5 Tax and Billing
- Configure applicable tax rates.
- Configure GST details.
- Manage tax-inclusive pricing.
- Manage tax-exclusive pricing.
- Configure invoice details.
- Add business tax information.
- Generate invoices.
- View tax breakdowns.

## 2.6 Inventory Management
- Update stock.
- View available stock.
- Track low-stock products.
- Track out-of-stock products.
- Manage inventory variants.
- Perform bulk stock updates.
- Receive inventory notifications.
- View inventory history.

## 2.7 Order Management
- View incoming orders.
- Accept orders.
- Reject orders where permitted.
- Process orders.
- Update order status.
- Prepare shipments.
- Add tracking information.
- Handle returns.
- Handle cancellation requests.
- Manage fulfillment.

## 2.8 Dukaan vs Dukaan — Retailer Participation
- Receive customer demand requests.
- Submit offers.
- Submit quotations.
- Compete with other retailers.
- Offer bulk pricing.
- Respond to group-buy demand.
- Submit product availability.
- Respond to Demand Gap opportunities.

## 2.9 Demand Marketplace
- View demand for products.
- View customer demand trends.
- Respond to unmet demand.
- Offer products for demand requests.
- Participate in community purchasing.
- View demand volume.
- Submit bulk offers.

## 2.10 Retailer Analytics
- Sales revenue.
- Orders.
- Product performance.
- Inventory performance.
- Offer performance.
- Conversion metrics.
- Customer ratings.
- Best-selling products.
- Low-performing products.
- Profit and sales reports.

## 2.11 Retailer Profile and Verification
- Manage business registration details.
- Manage GST information.
- Manage bank details.
- Upload verification documents.
- View retailer verification status.
- Manage store information.

---

# 3. Customer / Purchaser Panel

Customers receive a shopping-focused experience. They must only see customer-facing features and must not have access to admin or retailer management tools.

## 3.1 Smart Shopping
- Search products.
- Browse categories.
- Filter products.
- Compare products.
- View product recommendations.
- Personalized shopping.
- AI-powered search.
- Natural-language shopping requests.

## 3.2 Basket Mission
- Create a shopping mission.
- Specify a budget.
- Specify requirements.
- Specify purpose.
- Generate a complete shopping basket.
- Automatically recommend suitable products.
- Optimize the basket within the budget.
- Remove or replace products.
- Modify the mission.

Example: "Set up my apartment with everything essential under ₹5,000." The system creates a suitable basket based on the user's budget and requirements.

## 3.3 Basket Intent Memory
- Remember unfinished shopping missions.
- Remember the original budget.
- Track spent money.
- Track remaining budget.
- Track purchased products.
- Track remaining requirements.
- Resume shopping from a previous session.

## 3.4 Basket Substitute Intelligence
- Find alternative products.
- Compare specifications.
- Compare prices.
- Compare quality.
- Compare compatibility.
- Recommend cheaper alternatives.
- Recommend better-value alternatives.
- Explain why an alternative is recommended.

## 3.5 Demand Gap Results
- Search for products.
- Detect unmet requirements.
- View similar customer demands.
- Join an existing demand pool.
- Create a new demand request.
- View demand progress.
- Receive offers from retailers.
- Get notified when requested products become available.

## 3.6 Basket Community Buying
- Join group purchases.
- Create group purchases.
- Invite friends.
- Invite communities.
- View group progress.
- See quantity thresholds.
- Unlock bulk discounts.
- Purchase collectively.

## 3.7 Basket Community Exchange
- Request unavailable products.
- Join similar requests.
- Aggregate demand.
- Send combined demand to retailers.
- Receive retailer offers.
- Compare available offers.
- Purchase once demand is fulfilled.

## 3.8 AI Negotiator
- Set a target price.
- Set a maximum budget.
- Ask AI to find better deals.
- Compare retailers.
- Negotiate available offers where supported.
- Analyze discount opportunities.
- Suggest alternative products.
- Recommend the best purchasing option.

## 3.9 Dukaan vs Dukaan
- Submit product requirements.
- Receive offers from multiple retailers.
- Compare prices.
- Compare delivery times.
- Compare warranties.
- Compare retailer ratings.
- Compare discounts.
- Choose the best offer.

## 3.10 Basket Price Intelligence
- View historical price information.
- View price trends.
- View lowest recorded prices.
- View highest recorded prices.
- View current price versus historical average.
- Identify genuine discounts.
- Access price information through a product information button.

## 3.11 Basket Product Passport
- View purchased products.
- Store invoices.
- Store warranty information.
- Store purchase dates.
- Track warranty expiry.
- View service information.
- View service-center details.
- Maintain product ownership history.
- Access maintenance information.
- Request service where supported.

## 3.12 Sale Stream
- Discover live deals.
- View flash sales.
- View trending products.
- View limited-time offers.
- View retailer promotions.
- View demand-based offers.
- View products with price drops.
- Discover new deals.

**Sale Stream Rewind is removed from the finalized feature list.**

## 3.13 Bharat Multilingual
- Shop in multiple Indian languages.
- Search in regional languages.
- Interact with AI in regional languages.
- Translate product information.
- Translate offers.
- Use multilingual shopping assistance.

## 3.14 Optional — Handwritten List to Shopping Basket
- Upload a handwritten shopping list.
- Convert handwriting to text.
- Detect product names.
- Detect quantities.
- Correct OCR errors.
- Match list items with products.
- Generate a shopping basket.
- Review extracted items before purchasing.

This feature is optional and is not part of the mandatory core feature set.

## 3.15 Customer Account and Shopping
- Profile management.
- Address management.
- Wishlist.
- Shopping cart.
- Checkout.
- Orders.
- Order tracking.
- Payment history.
- Returns.
- Refunds.
- Ratings and reviews.
- Notifications.

---

# 4. Feature Ownership Matrix

| Feature | Admin | Retailer | Customer |
|---|---|---|---|
| Create platform products | Yes | No | No |
| Manage categories | Yes | No | No |
| Approve products | Yes | No | No |
| Create platform deals | Yes | No | No |
| Create retailer deals | No | Yes | No |
| Upload product images | Yes | Yes | No |
| Manage product listings | Platform catalogue | Own listings | View |
| Set retailer prices | No | Yes | No |
| Manage tax configuration | Platform rules | Own tax details | View tax |
| Manage inventory | Monitor | Own inventory | View availability |
| Manage orders | All orders | Own orders | Own orders |
| Manage retailers | Yes | No | No |
| Manage customers | Yes | No | Own profile |
| Basket Mission | Configure/monitor | Respond to demand | Use |
| Basket Intent Memory | Platform support | No | Use |
| Substitute Intelligence | Configure system | Provide alternatives | Use |
| Demand Gap | Manage | Respond to demand | Create/join |
| Community Buying | Manage | Supply offers | Join/create |
| Community Exchange | Manage | Respond | Create/join |
| AI Negotiator | Monitor | Respond to offers | Use |
| Dukaan vs Dukaan | Manage | Participate | Compare offers |
| Price Intelligence | Manage data | Submit pricing | View |
| Product Passport | Manage system | Provide warranty info | Access |
| Sale Stream | Manage platform feed | Submit deals | Discover |
| Bharat Multilingual | Configure | Use | Use |
| Handwritten List | Configure AI | No | Optional use |

---

# 5. Final Feature List by Role

## Admin
1. Product Management
2. Platform Deals and Promotions
3. Retailer Management
4. Customer Management
5. Demand Intelligence Management
6. Dukaan vs Dukaan Management
7. Tax and Pricing Configuration
8. Order and Transaction Management
9. Analytics and Reports
10. Platform Configuration

## Retailer
1. Store Management
2. Product Listings
3. Product Pricing
4. Retailer Offers and Discounts
5. Tax and Billing
6. Inventory Management
7. Order Management
8. Dukaan vs Dukaan Participation
9. Demand Marketplace
10. Retailer Analytics
11. Retailer Profile and Verification

## Customer / Purchaser
1. Smart Shopping
2. Basket Mission
3. Basket Intent Memory
4. Basket Substitute Intelligence
5. Demand Gap Results
6. Basket Community Buying
7. Basket Community Exchange
8. AI Negotiator
9. Dukaan vs Dukaan
10. Basket Price Intelligence
11. Basket Product Passport
12. Sale Stream
13. Bharat Multilingual
14. Handwritten List to Shopping Basket (Optional)
15. Customer Account and Shopping

---

# 6. Role-Based Access Control Requirement

The application must implement three primary roles:

- **ADMIN** — platform-wide management and control.
- **RETAILER** — management of their own store, products, pricing, inventory, offers, orders, and retailer marketplace participation.
- **CUSTOMER** — shopping, purchasing, demand participation, and customer-specific features.

Each role must have:
- A dedicated dashboard.
- Role-specific navigation.
- Role-specific UI components and workflows.
- Permissions enforced by the backend/API.
- Access restrictions preventing users from accessing another role's protected functions.

Frontend visibility controls are not sufficient. Backend authorization must validate the role and, where applicable, ownership of the resource on every protected operation.

---

# 7. Removed and Optional Features

| Feature | Status |
|---|---|
| Sale Stream Rewind | Removed |
| Handwritten List to Shopping Basket | Optional |
| Admin features exposed to customers | Prohibited |
| Retailer administrative privileges | Prohibited |
| Platform-wide product management by retailers | Prohibited |

---

# 8. Product Vision

The platform's shopping flow is intended to work as follows:

1. **Customer Mission** — the customer explains what they need and their budget.
2. **Basket Mission AI** — the platform creates an optimized shopping basket.
3. **Shopping Intelligence** — the platform finds alternatives, compares prices, analyzes pricing, and remembers the mission.
4. **Demand Intelligence** — the platform identifies unmet demand and groups customers with similar requirements.
5. **Vendor Competition** — retailers compete through Dukaan vs Dukaan and respond to demand.
6. **Best Purchase** — the customer receives the best available combination of price, quality, availability, and convenience.
7. **Product Ownership** — the Basket Product Passport stores warranty, invoice, service, and ownership information after purchase.

The platform's core differentiators are:

- **Basket Mission:** Tell the platform what you need; it creates a shopping solution.
- **Demand Gap and Community Buying:** If enough customers want something, the platform can aggregate demand and help source it at a better price or make it available.
- **AI Negotiator and Dukaan vs Dukaan:** The platform helps customers find, compare, and negotiate the best deal instead of simply accepting a listed price.
