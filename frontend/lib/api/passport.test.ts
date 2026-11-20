import test from "node:test";
import assert from "node:assert/strict";
import { apiClient } from "./client.ts";
import type {
  PublicProductPassport,
  PublicListingPassport,
  RetailerListingPassportDetail,
  RetailerClaim,
  AdminClaim,
  AdminClaimQueueResponse,
} from "@/types";

test("Product Passport API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockPublicPassport: PublicProductPassport = {
    id: "pass-123",
    product_id: "prod-456",
    product_name: "Noise Cancelling Headphones",
    brand: "AcoustiQ",
    category_name: "Audio",
    manufacturer: "AcoustiQ Audio Ltd.",
    country_of_origin: "India",
    model_number: "AQ-NC900",
    gtin_ean_upc: "8901234567890",
    materials: ["Aluminium", "Memory Foam"],
    technical_specs: { battery_hours: 35 },
    package_contents: ["Headphones", "USB Cable"],
    warranty_info: "1 Year Manufacturer Warranty",
    certifications: ["BIS", "CE"],
    claims: [
      {
        id: "claim-1",
        claim_scope: "PRODUCT",
        claim_type: "CERTIFICATION",
        claim_key: "bis_certified",
        claim_value: "BIS Standard R-41000000",
        review_status: "VERIFIED",
        is_public_evidence: true,
        evidence_url: "https://bis.gov.in/cert.pdf",
        created_at: "2026-11-20T10:00:00Z",
      },
    ],
    available_listings: [
      {
        listing_id: "lst-789",
        retailer_id: "ret-101",
        retailer_name: "Tech Hub",
        selling_price_paise: 99900,
        is_in_stock: true,
        item_condition: "NEW",
      },
    ],
  };

  await t.test("getProductPassport calls /api/v1/products/{id}/passport", async () => {
    globalThis.fetch = async (input, init) => {
      const url = String(input);
      assert.match(url, /\/api\/v1\/products\/prod-456\/passport\?listing_id=lst-789/);
      assert.equal(init?.method || "GET", "GET");
      return new Response(JSON.stringify(mockPublicPassport), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getProductPassport("prod-456", "lst-789");
    assert.equal(res.product_name, "Noise Cancelling Headphones");
    assert.equal(res.manufacturer, "AcoustiQ Audio Ltd.");
    assert.equal(res.claims[0].review_status, "VERIFIED");
  });

  await t.test("getListingPassport calls /api/v1/passport/listings/{listingId}", async () => {
    const mockListingPassport: PublicListingPassport = {
      id: "lst-pass-1",
      listing_id: "lst-789",
      retailer_id: "ret-101",
      retailer_name: "Tech Hub",
      item_condition: "REFURBISHED",
      seller_warranty: "6 Months Seller Replacement Warranty",
      claims: [],
      created_at: "2026-11-20T10:00:00Z",
      updated_at: "2026-11-20T10:00:00Z",
    };

    globalThis.fetch = async (input) => {
      const url = String(input);
      assert.match(url, /\/api\/v1\/passport\/listings\/lst-789/);
      return new Response(JSON.stringify(mockListingPassport), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getListingPassport("lst-789");
    assert.equal(res.item_condition, "REFURBISHED");
    assert.equal(res.seller_warranty, "6 Months Seller Replacement Warranty");
  });

  await t.test("upsertRetailerListingPassport sends PUT to /retailer/passport/listings/{id}", async () => {
    const mockDetail: RetailerListingPassportDetail = {
      id: "lst-pass-1",
      listing_id: "lst-789",
      retailer_id: "ret-101",
      item_condition: "REFURBISHED",
      seller_warranty: "3 Months Warranty",
      claims: [],
      created_at: "2026-11-20T10:00:00Z",
      updated_at: "2026-11-20T10:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      assert.match(String(input), /\/api\/v1\/retailer\/passport\/listings\/lst-789/);
      assert.equal(init?.method, "PUT");
      const body = JSON.parse(init?.body as string);
      assert.equal(body.item_condition, "REFURBISHED");
      return new Response(JSON.stringify(mockDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.upsertRetailerListingPassport("lst-789", {
      item_condition: "REFURBISHED",
      seller_warranty: "3 Months Warranty",
    });
    assert.equal(res.item_condition, "REFURBISHED");
  });

  await t.test("submitRetailerClaim sends POST to /retailer/passport/listings/{id}/claims", async () => {
    const mockClaim: RetailerClaim = {
      id: "claim-new",
      listing_id: "lst-789",
      claim_scope: "LISTING",
      claim_type: "CERTIFICATION",
      claim_key: "agmark",
      claim_value: "Agmark Grade 1",
      evidence_type: "CERTIFICATE",
      is_public_evidence: true,
      review_status: "PENDING",
      created_at: "2026-11-20T10:00:00Z",
      updated_at: "2026-11-20T10:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      assert.match(String(input), /\/api\/v1\/retailer\/passport\/listings\/lst-789\/claims/);
      assert.equal(init?.method, "POST");
      return new Response(JSON.stringify(mockClaim), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.submitRetailerClaim("lst-789", {
      claim_scope: "LISTING",
      claim_type: "CERTIFICATION",
      claim_key: "agmark",
      claim_value: "Agmark Grade 1",
    });
    assert.equal(res.review_status, "PENDING");
  });

  await t.test("admin moderation queue, verify, and reject", async () => {
    const mockQueue: AdminClaimQueueResponse = {
      items: [
        {
          id: "claim-q1",
          claim_scope: "LISTING",
          claim_type: "CERTIFICATION",
          claim_key: "agmark",
          claim_value: "Agmark Grade 1",
          evidence_type: "CERTIFICATE",
          is_public_evidence: true,
          review_status: "PENDING",
          created_at: "2026-11-20T10:00:00Z",
          updated_at: "2026-11-20T10:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      limit: 20,
      pages: 1,
    };

    globalThis.fetch = async (input, init) => {
      const url = String(input);
      if (url.includes("/admin/passport/queue")) {
        return new Response(JSON.stringify(mockQueue), { status: 200 });
      }
      if (url.includes("/verify")) {
        assert.equal(init?.method, "POST");
        const verified: AdminClaim = { ...mockQueue.items[0], review_status: "VERIFIED" };
        return new Response(JSON.stringify(verified), { status: 200 });
      }
      if (url.includes("/reject")) {
        assert.equal(init?.method, "POST");
        const body = JSON.parse(init?.body as string);
        assert.equal(body.rejection_reason, "Document expired");
        const rejected: AdminClaim = {
          ...mockQueue.items[0],
          review_status: "REJECTED",
          rejection_reason: "Document expired",
        };
        return new Response(JSON.stringify(rejected), { status: 200 });
      }
      throw new Error(`Unhandled url ${url}`);
    };

    const q = await apiClient.getAdminClaimsQueue({ status: "PENDING" });
    assert.equal(q.items.length, 1);
    assert.equal(q.items[0].review_status, "PENDING");

    const verified = await apiClient.verifyAdminClaim("claim-q1");
    assert.equal(verified.review_status, "VERIFIED");

    const rejected = await apiClient.rejectAdminClaim("claim-q1", "Document expired");
    assert.equal(rejected.review_status, "REJECTED");
    assert.equal(rejected.rejection_reason, "Document expired");
  });
});
