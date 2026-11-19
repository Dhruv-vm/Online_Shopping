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
});
