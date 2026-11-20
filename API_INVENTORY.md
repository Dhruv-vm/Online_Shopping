# BASKET — Comprehensive API Inventory & Endpoint Reference

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Base Path:** `/api/v1`  
> **Last Updated:** 2026-11-20  

---

## 1. System & Observability Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Health | None | Public | Liveness probe returning process state | `200 OK` |
| `GET` | `/ready` | Health | None | Public | Readiness probe checking DB, Kafka, OpenSearch | `200 OK`, `503 Unavailable` |
| `GET` | `/metrics` | Observability | None | Internal | Prometheus metrics in text format 0.0.4 | `200 OK` |
| `GET` | `/api/v1/info` | System | None | Public | Service metadata, environment, and API version | `200 OK` |

---

## 2. Identity, Authentication & Profile Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Authentication | None | Public | Register customer account | `RegisterRequest` | `201 Created` |
| `POST` | `/api/v1/auth/retailer/register` | Authentication | None | Public | Register retailer account | `RetailerRegisterRequest` | `201 Created` |
| `POST` | `/api/v1/auth/login` | Authentication | None | Public | Authenticate user, issue JWT cookies | `LoginRequest` | `200 OK` |
| `POST` | `/api/v1/auth/refresh` | Authentication | Refresh Cookie | Authenticated | Rotate access token via refresh token | None | `200 OK` |
| `POST` | `/api/v1/auth/logout` | Authentication | Access Token | Authenticated | Revoke current session & clear cookies | None | `200 OK` |
| `POST` | `/api/v1/auth/logout-all` | Authentication | Access Token | Authenticated | Revoke all active sessions for user | None | `200 OK` |
| `GET` | `/api/v1/users/me` | Users | Access Token | Authenticated | Fetch authenticated user profile & role | None | `200 OK` |
| `GET` | `/api/v1/addresses` | Addresses | Access Token | Customer | List saved delivery addresses | None | `200 OK` |
| `POST` | `/api/v1/addresses` | Addresses | Access Token | Customer | Add new delivery address | `AddressCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/addresses/{address_id}` | Addresses | Access Token | Customer | Update existing address details | `AddressUpdateRequest` | `200 OK` |
| `DELETE`| `/api/v1/addresses/{address_id}` | Addresses | Access Token | Customer | Delete saved address | None | `200 OK` |

---

## 3. Public Catalogue & Taxonomy Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Query Parameters | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/catalogue/categories` | Catalogue | None | Public | List hierarchical category tree | `parent_id`, `is_active` | `200 OK` |
| `GET` | `/api/v1/categories` | Catalogue | None | Public | Alias for category listing | `parent_id` | `200 OK` |
| `GET` | `/api/v1/catalogue/products` | Catalogue | None | Public | Browse products with pagination | `category_id`, `brand`, `page` | `200 OK` |
| `GET` | `/api/v1/products` | Catalogue | None | Public | Alias for product listing | `category_id`, `brand`, `page` | `200 OK` |
| `GET` | `/api/v1/catalogue/products/{id}` | Catalogue | None | Public | Get canonical product details & variants | None | `200 OK` |
| `GET` | `/api/v1/products/{id}` | Catalogue | None | Public | Alias for product detail | None | `200 OK` |
| `GET` | `/api/v1/catalogue/retailers` | Catalogue | None | Public | List verified public retailers | `city`, `is_active` | `200 OK` |
| `GET` | `/api/v1/retailers` | Catalogue | None | Public | Alias for retailer listing | `city` | `200 OK` |

---

## 4. Search & Discovery Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Query Parameters | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/search` | Search | None | Public | Faceted search with OpenSearch & DB fallback | `q`, `category`, `price_min`, `price_max` | `200 OK` |
| `GET` | `/api/v1/search/suggestions` | Search | None | Public | Autocomplete query suggestions | `q`, `limit` | `200 OK` |

---

## 5. Universal Shopping Cart Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/cart` | Cart | Session / Token | Guest / Customer | Retrieve active cart with computed prices | None | `200 OK` |
| `DELETE`| `/api/v1/cart` | Cart | Session / Token | Guest / Customer | Clear all items from active cart | None | `200 OK` |
| `POST` | `/api/v1/cart/items` | Cart | Session / Token | Guest / Customer | Add listing item to cart | `CartItemCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/cart/items/{item_id}`| Cart | Session / Token | Guest / Customer | Update quantity of cart item | `CartItemUpdateRequest` | `200 OK` |
| `DELETE`| `/api/v1/cart/items/{item_id}`| Cart | Session / Token | Guest / Customer | Remove specific item from cart | None | `200 OK` |
| `POST` | `/api/v1/cart/merge` | Cart | Access Token | Customer | Merge guest session cart into user cart | `CartMergeRequest` | `200 OK` |

---

## 6. Pricing, Deals & Cryptographic Quotes

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/checkout/quote` | Pricing | Session / Token | Guest / Customer | Generate HMAC-signed checkout quote | `QuoteCreateRequest` | `201 Created` |
| `POST` | `/api/v1/quotes` | Pricing | Session / Token | Guest / Customer | Alias for quote creation | `QuoteCreateRequest` | `201 Created` |
| `GET` | `/api/v1/quotes` | Pricing | Access Token | Customer | List historical quotes for user | None | `200 OK` |
| `GET` | `/api/v1/quotes/{quote_id}` | Pricing | Access Token | Customer | Fetch specific quote details | None | `200 OK` |
| `POST` | `/api/v1/quotes/{quote_id}/validate` | Pricing | Session / Token | Guest / Customer | Validate HMAC signature & expiration | None | `200 OK` |
| `POST` | `/api/v1/quotes/{quote_id}/refresh` | Pricing | Session / Token | Guest / Customer | Refresh expired quote prices | None | `200 OK` |

---

## 7. Inventory Reservations & Concurrency

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reservations` | Inventory | Access Token | Customer | Lock stock for 10 min using row locks | `ReservationCreateRequest` | `201 Created` |
| `GET` | `/api/v1/reservations/{reservation_id}` | Inventory | Access Token | Customer | Check reservation status & TTL | None | `200 OK` |
| `POST` | `/api/v1/reservations/{reservation_id}/release`| Inventory | Access Token | Customer | Manually release stock reservation | None | `200 OK` |

---

## 8. Orders, Shipments & Returns Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/orders` | Orders | Access Token | Customer | List customer orders | None | `200 OK` |
| `POST` | `/api/v1/orders` | Orders | Access Token | Customer | Place order with quote & reservation | `OrderCreateRequest` | `201 Created` |
| `GET` | `/api/v1/orders/{order_id}` | Orders | Access Token | Customer | Fetch order details & item snapshots | None | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Orders | Access Token | Customer | Cancel unfulfilled order | `OrderCancelRequest` | `200 OK` |
| `GET` | `/api/v1/orders/{order_id}/tracking` | Orders | Access Token | Customer | Track order fulfillment timeline | None | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/shipments` | Orders | Access Token | Admin / Retailer | Create shipment & tracking number | `ShipmentCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/orders/{order_id}/shipments/{shipment_id}`| Orders | Access Token | Admin / Retailer | Update courier dispatch status | `ShipmentUpdateRequest` | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/returns` | Orders | Access Token | Customer | Request post-delivery item return | `ReturnCreateRequest` | `201 Created` |
| `GET` | `/api/v1/orders/{order_id}/returns` | Orders | Access Token | Customer | List return requests for order | None | `200 OK` |
| `PATCH`| `/api/v1/returns/{return_id}/status` | Orders | Access Token | Retailer / Admin | Approve or reject return request | `ReturnStatusUpdateRequest`| `200 OK` |

---

## 9. Payments & Razorpay Integration Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/orders/{order_id}/payments` | Payments | Access Token | Customer | Create Razorpay order | `PaymentInitiateRequest` | `201 Created` |
| `POST` | `/api/v1/orders/{order_id}/payments/verify` | Payments | Access Token | Customer | Verify Razorpay payment signature | `PaymentVerifyRequest` | `200 OK` |
| `POST` | `/api/v1/payments/webhook` | Payments | Webhook HMAC | Razorpay Service| Ingest Razorpay asynchronous webhooks | Webhook Payload | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/refunds` | Payments | Access Token | Admin | Issue partial or full order refund | `RefundCreateRequest` | `201 Created` |

---

## 10. Customer Intelligence: Basket Mission (Phase 2A)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/missions/plan` | Basket Mission | None / Token | Public / Customer | Generate budget-optimized knapsack basket | `MissionPlanRequest` | `200 OK` |
| `GET` | `/api/v1/missions/thematic` | Basket Mission | None / Token | Public / Customer | Get curated thematic shopping missions | `theme_id` | `200 OK` |
| `POST` | `/api/v1/missions/sync-to-cart`| Basket Mission | Session / Token | Guest / Customer | Sync mission items into active cart | `MissionSyncRequest` | `200 OK` |

---

## 11. Customer Intelligence: Substitute Intelligence (Phase 2B)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/substitutes/listings/{listing_id}` | Substitutes | None / Token | Public / Customer | Get 5-tier ranked product alternatives | `tier`, `max_price` | `200 OK` |
| `GET` | `/api/v1/cart/items/{item_id}/substitutes` | Cart | Session / Token | Guest / Customer | Get alternatives for item in cart | None | `200 OK` |
| `POST` | `/api/v1/cart/items/{item_id}/replace` | Cart | Session / Token | Guest / Customer | Atomically replace cart item with alternative | `CartItemReplaceRequest` | `200 OK` |

---

## 12. Customer Intelligence: Basket Intent Memory (Phase 2C)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/intent/overview` | Intent Memory | Access Token | Customer | Get customer intent profile & recurring items| None | `200 OK` |
| `GET` | `/api/v1/intent/profile` | Intent Memory | Access Token | Customer | Get preference profile | None | `200 OK` |
| `PUT` | `/api/v1/intent/profile` | Intent Memory | Access Token | Customer | Upsert dietary & brand preferences | `IntentProfileUpsertRequest` | `200 OK` |
| `PATCH`| `/api/v1/intent/consent` | Intent Memory | Access Token | Customer | Explicitly toggle personalization consent | `ConsentUpdateRequest` | `200 OK` |
| `GET` | `/api/v1/intent/memories` | Intent Memory | Access Token | Customer | List recurring shopping intentions | None | `200 OK` |
| `POST` | `/api/v1/intent/memories` | Intent Memory | Access Token | Customer | Create recurring intention card | `RecurringIntentionCreate` | `201 Created` |
| `DELETE`| `/api/v1/intent/memories/{id}`| Intent Memory | Access Token | Customer | Delete specific recurring intention | None | `200 OK` |
| `DELETE`| `/api/v1/intent/clear-all` | Intent Memory | Access Token | Customer | Complete erasure of all intent memory data | None | `200 OK` |

---

## 13. Customer Intelligence: Product Passport (Phase 2D)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/passport/products/{id}` | Product Passport | None | Public | Get canonical product specifications | None | `200 OK` |
| `GET` | `/api/v1/products/{id}/passport` | Product Passport | None | Public | Alias for product passport | None | `200 OK` |
| `GET` | `/api/v1/passport/listings/{listing_id}`| Product Passport | None | Public | Get retailer listing passport & verified claims| None | `200 OK` |
| `GET` | `/api/v1/retailer/passport/listings/{id}`| Retailer Passport | Access Token | Retailer | Get store listing passport details | None | `200 OK` |
| `PUT` | `/api/v1/retailer/passport/listings/{id}`| Retailer Passport | Access Token | Retailer | Upsert listing batch, warranty, specs | `ListingPassportUpsert` | `200 OK` |
| `POST` | `/api/v1/retailer/passport/listings/{id}/claims`| Retailer Passport | Access Token | Retailer | Submit listing claim for moderation | `ClaimSubmitRequest` | `201 Created` |
| `GET` | `/api/v1/retailer/passport/claims` | Retailer Passport | Access Token | Retailer | List submitted claims and verification states | None | `200 OK` |
| `PUT` | `/api/v1/retailer/passport/claims/{id}` | Retailer Passport | Access Token | Retailer | Edit claim (auto-resets to PENDING) | `ClaimUpdateRequest` | `200 OK` |
| `GET` | `/api/v1/retailer/passport/claims/{id}/history`| Retailer Passport | Access Token | Retailer | View immutable revision & review history | None | `200 OK` |
| `GET` | `/api/v1/admin/passport/queue` | Admin Passport | Access Token | Admin | Review pending claims moderation queue | `status`, `page` | `200 OK` |
| `POST` | `/api/v1/admin/passport/claims/{id}/verify` | Admin Passport | Access Token | Admin | Approve & verify claim with auditor notes | None | `200 OK` |
| `POST` | `/api/v1/admin/passport/claims/{id}/reject` | Admin Passport | Access Token | Admin | Reject claim with mandatory reason | `ClaimRejectRequest` | `200 OK` |
| `GET` | `/api/v1/admin/passport/claims/{id}/history`| Admin Passport | Access Token | Admin | Inspect complete review decision audit trail | None | `200 OK` |
| `PUT` | `/api/v1/admin/passport/products/{id}` | Admin Passport | Access Token | Admin | Create or update canonical product passport | `CanonicalPassportUpsert`| `200 OK` |

---

## 14. Retailer Management Portal (`/api/v1/retailer/*`)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/retailer/overview` | Retailer Portal | Access Token | Retailer | Store KPI metrics, sales, and low-stock alerts | `200 OK` |
| `GET` | `/api/v1/retailer/profile` | Retailer Portal | Access Token | Retailer | Fetch store profile, GSTIN, and business details | `200 OK` |
| `PUT` | `/api/v1/retailer/profile` | Retailer Portal | Access Token | Retailer | Update store profile details | `200 OK` |
| `GET` | `/api/v1/retailer/catalogue/products` | Retailer Portal | Access Token | Retailer | Browse global catalogue to map listings | `200 OK` |
| `POST` | `/api/v1/retailer/products` | Retailer Portal | Access Token | Retailer | Request custom product addition to catalogue | `201 Created` |
| `GET` | `/api/v1/retailer/listings` | Retailer Portal | Access Token | Retailer | List store product listings and active status | `200 OK` |
| `POST` | `/api/v1/retailer/listings` | Retailer Portal | Access Token | Retailer | Create new listing from product variant | `201 Created` |
| `GET` | `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Get listing details and pricing | `200 OK` |
| `PUT` | `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Update listing price or active state | `200 OK` |
| `DELETE`| `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Soft-delete / deactivate listing | `200 OK` |
| `GET` | `/api/v1/retailer/inventory` | Retailer Portal | Access Token | Retailer | Inventory overview across all listings | `200 OK` |
| `POST` | `/api/v1/retailer/listings/{id}/inventory` | Retailer Portal | Access Token | Retailer | Adjust stock quantity for single listing | `200 OK` |
| `POST` | `/api/v1/retailer/inventory/bulk-adjust` | Retailer Portal | Access Token | Retailer | Bulk update inventory levels via batch payload | `200 OK` |
| `GET` | `/api/v1/retailer/orders` | Retailer Portal | Access Token | Retailer | List orders containing store listings | `200 OK` |
| `GET` | `/api/v1/retailer/orders/{id}` | Retailer Portal | Access Token | Retailer | View itemized fulfillment details | `200 OK` |
| `PATCH`| `/api/v1/retailer/orders/{id}/status` | Retailer Portal | Access Token | Retailer | Update item dispatch / fulfillment state | `200 OK` |
| `GET` | `/api/v1/retailer/offers` | Retailer Portal | Access Token | Retailer | List store promotional discounts | `200 OK` |
| `POST` | `/api/v1/retailer/offers` | Retailer Portal | Access Token | Retailer | Create store-specific discount campaign | `201 Created` |
| `PUT` | `/api/v1/retailer/offers/{id}` | Retailer Portal | Access Token | Retailer | Modify offer parameters | `200 OK` |
| `DELETE`| `/api/v1/retailer/offers/{id}` | Retailer Portal | Access Token | Retailer | Terminate active offer | `200 OK` |
| `GET` | `/api/v1/retailer/analytics` | Retailer Portal | Access Token | Retailer | Revenue, order volume, and return analytics | `200 OK` |

---

## 15. Administrator Management Portal (`/api/v1/admin/*`)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/overview` | Admin Portal | Access Token | Admin | Platform GMV, orders, user count, active stores | `200 OK` |
| `GET` | `/api/v1/admin/retailers` | Admin Portal | Access Token | Admin | List all registered retailers with verification state | `200 OK` |
| `GET` | `/api/v1/admin/retailers/{id}` | Admin Portal | Access Token | Admin | Retailer compliance & business profile details | `200 OK` |
| `POST` | `/api/v1/admin/retailers/{id}/verify` | Admin Portal | Access Token | Admin | Verify and activate retailer for public sales | `200 OK` |
| `POST` | `/api/v1/admin/retailers/{id}/documents/{doc_id}/verify` | Admin Portal | Access Token | Admin | Verify uploaded GSTIN / PAN / FSSAI document | `200 OK` |
| `GET` | `/api/v1/admin/retailers/{id}/analytics` | Admin Portal | Access Token | Admin | Performance audit for specific store | `200 OK` |
| `GET` | `/api/v1/admin/catalogue/categories` | Admin Portal | Access Token | Admin | Manage global category tree | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/categories` | Admin Portal | Access Token | Admin | Add new category to global hierarchy | `201 Created` |
| `GET` | `/api/v1/admin/catalogue/products` | Admin Portal | Access Token | Admin | List canonical catalogue products | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/products` | Admin Portal | Access Token | Admin | Create new canonical product | `201 Created` |
| `GET` | `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Canonical product detail with variants | `200 OK` |
| `PUT` | `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Update canonical product specs & brand | `200 OK` |
| `DELETE`| `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Soft-delete / deactivate product | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/products/{id}/variants` | Admin Portal | Access Token | Admin | Add SKU variant to product | `201 Created` |
| `PUT` | `/api/v1/admin/catalogue/variants/{id}` | Admin Portal | Access Token | Admin | Update variant attributes & MRP | `200 OK` |
| `DELETE`| `/api/v1/admin/catalogue/variants/{id}` | Admin Portal | Access Token | Admin | Deactivate variant SKU | `200 OK` |
| `GET` | `/api/v1/admin/deals` | Admin Portal | Access Token | Admin | List platform-wide deals | `200 OK` |
| `POST` | `/api/v1/admin/deals` | Admin Portal | Access Token | Admin | Create platform-sponsored deal | `201 Created` |
| `GET` | `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Fetch deal parameters | `200 OK` |
| `PUT` | `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Modify deal dates & percentages | `200 OK` |
| `DELETE`| `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Deactivate deal | `200 OK` |
