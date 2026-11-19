import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { apiClient } from "./client.ts";

describe("Admin and Retailer Portal API Client integration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("registerRetailer() posts onboarding payload and returns AuthResponse", async () => {
    globalThis.fetch = async (input, init) => {
      const url = String(input);
      assert.ok(url.includes("/api/v1/auth/retailer/register"));
      assert.equal(init?.method, "POST");

      const body = JSON.parse(String(init?.body));
      assert.equal(body.store_name, "Alpha Traders");
      assert.equal(body.state, "KA");
      assert.equal(body.email, "alpha@traders.com");

      return new Response(
        JSON.stringify({
          user: {
            id: "usr-ret-123",
            email: "alpha@traders.com",
            full_name: "Alpha Owner",
            role: "retailer",
            retailer_id: "ret-uuid-456",
            store_name: "Alpha Traders",
            verification_status: "PENDING",
            is_active: true,
            created_at: new Date().toISOString(),
          },
          access_token: "mock-jwt-token",
          refresh_token: "mock-refresh-token",
          csrf_token: "mock-csrf-token",
          token_type: "bearer",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await apiClient.registerRetailer({
      email: "alpha@traders.com",
      password: "Password123!",
      full_name: "Alpha Owner",
      phone: "+919876543210",
      store_name: "Alpha Traders",
      state: "KA",
      business_address: "123 Market Rd, Bengaluru",
    });

    assert.equal(res.user.role, "retailer");
    assert.equal(res.user.retailer_id, "ret-uuid-456");
    assert.equal(res.user.store_name, "Alpha Traders");
    assert.equal(res.user.verification_status, "PENDING");
  });

  it("getRetailerProfile() and updateRetailerProfile() invoke correct endpoints", async () => {
    let putCalled = false;
    globalThis.fetch = async (input, init) => {
      const url = String(input);
      if (init?.method === "PUT") {
        putCalled = true;
        assert.ok(url.includes("/api/v1/retailer/profile"));
        const body = JSON.parse(String(init?.body));
        assert.equal(body.is_open, false);
        return new Response(
          JSON.stringify({
            id: "ret-uuid-456",
            name: "Alpha Traders",
            slug: "alpha-traders",
            is_open: false,
            verification_status: "VERIFIED",
            is_active: true,
            created_at: new Date().toISOString(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      assert.ok(url.includes("/api/v1/retailer/profile"));
      return new Response(
        JSON.stringify({
          id: "ret-uuid-456",
          name: "Alpha Traders",
          slug: "alpha-traders",
          is_open: true,
          verification_status: "VERIFIED",
          is_active: true,
          created_at: new Date().toISOString(),
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const profile = await apiClient.getRetailerProfile();
    assert.equal(profile.name, "Alpha Traders");
    assert.equal(profile.is_open, true);

    const updated = await apiClient.updateRetailerProfile({ is_open: false });
    assert.equal(putCalled, true);
    assert.equal(updated.is_open, false);
  });

  it("getAdminOverview() and verifyRetailer() invoke admin endpoints", async () => {
    let verifyCalled = false;
    globalThis.fetch = async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/admin/retailers/ret-123/verify")) {
        verifyCalled = true;
        assert.equal(init?.method, "POST");
        const body = JSON.parse(String(init?.body));
        assert.equal(body.status, "VERIFIED");
        return new Response(
          JSON.stringify({
            id: "ret-123",
            name: "Beta Store",
            slug: "beta-store",
            verification_status: "VERIFIED",
            is_active: true,
            is_open: true,
            created_at: new Date().toISOString(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      assert.ok(url.includes("/api/v1/admin/overview"));
      return new Response(
        JSON.stringify({
          total_orders: 42,
          total_revenue_paise: 9990000,
          total_customers: 150,
          total_retailers: 12,
          pending_verifications: 2,
          active_products: 85,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const overview = await apiClient.getAdminOverview();
    assert.equal(overview.total_orders, 42);
    assert.equal(overview.total_revenue_paise, 9990000);

    const verified = await apiClient.verifyRetailer("ret-123", "VERIFIED");
    assert.equal(verifyCalled, true);
    assert.equal(verified.verification_status, "VERIFIED");
  });

  it("Retailer Listings and Inventory API Client methods invoke endpoints correctly", async () => {
    let createCalled = false;
    let adjustCalled = false;

    globalThis.fetch = async (input, init) => {
      const url = String(input);

      if (url.includes("/api/v1/retailer/catalogue/products")) {
        return new Response(
          JSON.stringify([
            {
              id: "prod-1",
              name: "Flagship Phone",
              brand: "BASKET",
              category_id: "cat-1",
              category_name: "Smartphones",
              description: "Latest model",
              image_url: "https://example.com/img.jpg",
              variants: [
                {
                  id: "var-1",
                  name: "128GB Black",
                  sku: "SKU-BLK-128",
                  attributes: { color: "Black" },
                  is_active: true,
                  is_already_listed: false,
                },
              ],
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/inventory") && init?.method === "POST") {
        adjustCalled = true;
        const body = JSON.parse(String(init?.body));
        assert.equal(body.adjustment_type, "SET");
        assert.equal(body.quantity, 50);
        return new Response(
          JSON.stringify({
            listing_id: "list-1",
            product_name: "Flagship Phone",
            variant_name: "128GB Black",
            sku: "SKU-BLK-128",
            seller_sku: "STORE-SKU-01",
            selling_price_paise: 499900,
            on_hand_quantity: 50,
            reserved_quantity: 2,
            available_quantity: 48,
            low_stock_threshold: 10,
            is_low_stock: false,
            is_out_of_stock: false,
            is_active: true,
            updated_at: new Date().toISOString(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.endsWith("/api/v1/retailer/listings") && init?.method === "POST") {
        createCalled = true;
        const body = JSON.parse(String(init?.body));
        assert.equal(body.variant_id, "var-1");
        assert.equal(body.selling_price_paise, 499900);
        return new Response(
          JSON.stringify({
            id: "list-1",
            retailer_id: "ret-1",
            variant_id: "var-1",
            product_id: "prod-1",
            product_name: "Flagship Phone",
            brand: "BASKET",
            category_name: "Smartphones",
            variant_name: "128GB Black",
            variant_sku: "SKU-BLK-128",
            variant_attributes: { color: "Black" },
            seller_sku: "STORE-SKU-01",
            original_price_paise: 549900,
            selling_price_paise: 499900,
            currency: "INR",
            hsn_code: "8517",
            gst_rate_basis_points: 1800,
            is_tax_verified: true,
            is_active: true,
            image_url: null,
            inventory: {
              on_hand_quantity: 30,
              reserved_quantity: 0,
              available_quantity: 30,
              low_stock_threshold: 5,
              is_low_stock: false,
              is_out_of_stock: false,
            },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/retailer/inventory") && (!init?.method || init?.method === "GET")) {
        return new Response(
          JSON.stringify({
            summary: {
              total_items: 1,
              total_on_hand_units: 30,
              total_reserved_units: 2,
              total_available_units: 28,
              low_stock_count: 0,
              out_of_stock_count: 0,
            },
            items: [
              {
                listing_id: "list-1",
                product_name: "Flagship Phone",
                variant_name: "128GB Black",
                sku: "SKU-BLK-128",
                seller_sku: "STORE-SKU-01",
                selling_price_paise: 499900,
                on_hand_quantity: 30,
                reserved_quantity: 2,
                available_quantity: 28,
                low_stock_threshold: 5,
                is_low_stock: false,
                is_out_of_stock: false,
                is_active: true,
                updated_at: new Date().toISOString(),
              },
            ],
            total: 1,
            limit: 50,
            offset: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
    };

    // 1. Catalogue lookup
    const prods = await apiClient.getRetailerCatalogueProducts({ search: "phone" });
    assert.equal(prods.length, 1);
    assert.equal(prods[0].name, "Flagship Phone");

    // 2. Create listing
    const listing = await apiClient.createRetailerListing({
      variant_id: "var-1",
      seller_sku: "STORE-SKU-01",
      original_price_paise: 549900,
      selling_price_paise: 499900,
      initial_on_hand_quantity: 30,
      low_stock_threshold: 5,
    });
    assert.equal(createCalled, true);
    assert.equal(listing.id, "list-1");
    assert.equal(listing.selling_price_paise, 499900);

    // 3. Inventory dashboard
    const invDash = await apiClient.getRetailerInventory();
    assert.equal(invDash.summary.total_available_units, 28);
    assert.equal(invDash.items.length, 1);

    // 4. Adjust inventory
    const adjusted = await apiClient.adjustRetailerInventory("list-1", {
      adjustment_type: "SET",
      quantity: 50,
      low_stock_threshold: 10,
    });
    assert.equal(adjustCalled, true);
    assert.equal(adjusted.on_hand_quantity, 50);
    assert.equal(adjusted.available_quantity, 48);
  });

  it("Admin Catalogue Management, Retailer Verification & Deals Client integration", async () => {
    let docVerifyCalled = false;
    let createProductCalled = false;
    let createDealCalled = false;

    globalThis.fetch = async (input, init) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url.includes("/api/v1/admin/retailers/ret-1/documents/doc-1/verify") && method === "POST") {
        docVerifyCalled = true;
        const body = JSON.parse(String(init?.body));
        return new Response(
          JSON.stringify({
            id: "doc-1",
            document_type: "GST_CERTIFICATE",
            document_url: "https://example.com/gst.pdf",
            status: body.status,
            rejection_reason: body.rejection_reason || null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/admin/catalogue/products") && method === "POST") {
        createProductCalled = true;
        const body = JSON.parse(String(init?.body));
        return new Response(
          JSON.stringify({
            id: "prod-canon-1",
            name: body.name,
            slug: "canonical-smart-tv",
            brand: body.brand,
            category_id: body.category_id,
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            images: [],
            variants: [
              {
                id: "var-canon-1",
                product_id: "prod-canon-1",
                name: "55 Inch OLED",
                sku: "TV-55-OLED",
                attributes: { size: "55 Inch" },
                is_active: true,
                created_at: new Date().toISOString(),
                listings_count: 0,
              },
            ],
            active_listings_count: 0,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/admin/deals") && method === "POST") {
        createDealCalled = true;
        const body = JSON.parse(String(init?.body));
        return new Response(
          JSON.stringify({
            id: "deal-festive-1",
            name: body.name,
            code: body.code || null,
            discount_type: body.discount_type,
            discount_value: body.discount_value,
            scope: body.scope,
            min_order_paise: body.min_order_paise || 0,
            times_used: 0,
            is_active: true,
            valid_from: new Date().toISOString(),
            status: "ACTIVE",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/admin/catalogue/products")) {
        return new Response(
          JSON.stringify([
            {
              id: "prod-canon-1",
              name: "Canonical Smart TV",
              slug: "canonical-smart-tv",
              brand: "VisionTech",
              category_id: "cat-1",
              is_active: true,
              variants_count: 1,
              listings_count: 0,
              created_at: new Date().toISOString(),
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/admin/deals")) {
        return new Response(
          JSON.stringify([
            {
              id: "deal-festive-1",
              name: "Festive Season 10% Off",
              discount_type: "PERCENTAGE",
              discount_value: 1000,
              scope: "PLATFORM_WIDE",
              min_order_paise: 0,
              times_used: 0,
              is_active: true,
              valid_from: new Date().toISOString(),
              status: "ACTIVE",
              created_at: new Date().toISOString(),
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    // 1. Verify retailer document
    const verifiedDoc = await apiClient.verifyAdminRetailerDocument("ret-1", "doc-1", "VERIFIED");
    assert.equal(docVerifyCalled, true);
    assert.equal(verifiedDoc.status, "VERIFIED");

    // 2. Create catalogue product
    const createdProduct = await apiClient.createAdminCatalogueProduct({
      category_id: "cat-1",
      name: "Canonical Smart TV",
      brand: "VisionTech",
      variants: [
        {
          name: "55 Inch OLED",
          sku: "TV-55-OLED",
          attributes: { size: "55 Inch" },
        },
      ],
    });
    assert.equal(createProductCalled, true);
    assert.equal(createdProduct.brand, "VisionTech");
    assert.equal(createdProduct.variants.length, 1);

    // 3. List catalogue products
    const products = await apiClient.listAdminCatalogueProducts();
    assert.equal(products.length, 1);
    assert.equal(products[0].name, "Canonical Smart TV");

    // 4. Create platform deal
    const createdDeal = await apiClient.createAdminDeal({
      name: "Festive Season 10% Off",
      code: "FESTIVE10",
      discount_type: "PERCENTAGE",
      discount_value: 1000,
      scope: "PLATFORM_WIDE",
    });
    assert.equal(createDealCalled, true);
    assert.equal(createdDeal.discount_value, 1000);
    assert.equal(createdDeal.status, "ACTIVE");

    // 5. List platform deals
    const deals = await apiClient.listAdminDeals();
    assert.equal(deals.length, 1);
    assert.equal(deals[0].name, "Festive Season 10% Off");
  });
});
