import test from "node:test";
import assert from "node:assert/strict";
import { apiClient } from "./client.ts";
import type {
  CustomerPreferenceProfile,
  RecurringIntention,
  IntentMemoryItem,
  IntentOverviewResponse,
  IntentSuggestionResponse,
  PersonalizationConsentResponse,
} from "@/types";

test("Basket Intent Memory API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockProfile: CustomerPreferenceProfile = {
    id: "prof-123",
    customer_id: "cust-123",
    preferred_brands: ["Sony", "Apple"],
    preferred_categories: ["cat-audio"],
    preferred_retailers: ["Basket Mart"],
    preferred_price_range: { min_paise: 100000, max_paise: 500000 },
    preferred_attributes: { color: "black" },
    shopping_priorities: ["QUALITY", "LOWEST_PRICE"],
    category_preferences: {},
    personalization_enabled: true,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  };

  const mockIntention: RecurringIntention = {
    id: "intent-123",
    customer_id: "cust-123",
    title: "Monthly Coffee Pods",
    category_ids: ["cat-groceries"],
    frequency: "MONTHLY",
    budget_paise: 250000,
    notes: "Medium roast only",
    is_active: true,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  };

  const mockMemory: IntentMemoryItem = {
    id: "mem-123",
    customer_id: "cust-123",
    memory_type: "PREFERENCE",
    key: "favorite_beans",
    value: { roast: "Arabica dark" },
    summary: "Prefers Arabica dark roast for weekend brews",
    source: "CUSTOMER_STATED",
    is_active: true,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
  };

  await t.test("getIntentOverview returns aggregated overview", async () => {
    const mockOverview: IntentOverviewResponse = {
      profile: mockProfile,
      recurring_intentions: [mockIntention],
      memories: [mockMemory],
      active_intentions_count: 1,
      total_memories_count: 1,
      personalization_enabled: true,
    };

    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/overview"
      );
      assert.strictEqual(init?.method, "GET");
      return new Response(JSON.stringify(mockOverview), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const result = await apiClient.getIntentOverview();
    assert.strictEqual(result.active_intentions_count, 1);
    assert.strictEqual(result.profile?.preferred_brands[0], "Sony");
    assert.strictEqual(result.recurring_intentions.length, 1);
    assert.strictEqual(result.memories.length, 1);
  });

  await t.test("getPreferenceProfile returns profile", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/profile"
      );
      assert.strictEqual(init?.method, "GET");
      return new Response(JSON.stringify(mockProfile), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const result = await apiClient.getPreferenceProfile();
    assert.strictEqual(result.id, "prof-123");
    assert.deepStrictEqual(result.preferred_brands, ["Sony", "Apple"]);
  });

  await t.test("updatePreferenceProfile sends put request with updated payload", async () => {
    let capturedBody: string | undefined;
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/profile"
      );
      assert.strictEqual(init?.method, "PUT");
      capturedBody = init?.body as string;
      return new Response(
        JSON.stringify({ ...mockProfile, preferred_brands: ["Bose"] }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await apiClient.updatePreferenceProfile({
      preferred_brands: ["Bose"],
    });
    assert.strictEqual(res.preferred_brands[0], "Bose");
    assert.ok(capturedBody?.includes("Bose"));
  });

  await t.test("updatePersonalizationConsent updates consent toggle", async () => {
    const mockConsent: PersonalizationConsentResponse = {
      personalization_enabled: false,
      updated_at: "2026-11-20T10:00:00Z",
      message: "Personalized recommendations disabled.",
    };

    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/consent"
      );
      assert.strictEqual(init?.method, "PATCH");
      return new Response(JSON.stringify(mockConsent), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.updatePersonalizationConsent(false);
    assert.strictEqual(res.personalization_enabled, false);
    assert.strictEqual(res.message, "Personalized recommendations disabled.");
  });

  await t.test("listRecurringIntentions passes active_only param when requested", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/recurring?active_only=true"
      );
      assert.strictEqual(init?.method, "GET");
      return new Response(JSON.stringify([mockIntention]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const list = await apiClient.listRecurringIntentions(true);
    assert.strictEqual(list.length, 1);
    assert.strictEqual(list[0].title, "Monthly Coffee Pods");
  });

  await t.test("createRecurringIntention sends post request", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/recurring"
      );
      assert.strictEqual(init?.method, "POST");
      return new Response(JSON.stringify(mockIntention), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.createRecurringIntention({
      title: "Monthly Coffee Pods",
      frequency: "MONTHLY",
      budget_paise: 250000,
    });
    assert.strictEqual(res.title, "Monthly Coffee Pods");
  });

  await t.test("toggleRecurringIntentionStatus sends patch", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/recurring/intent-123/status"
      );
      assert.strictEqual(init?.method, "PATCH");
      return new Response(
        JSON.stringify({ ...mockIntention, is_active: false }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await apiClient.toggleRecurringIntentionStatus("intent-123", false);
    assert.strictEqual(res.is_active, false);
  });

  await t.test("deleteRecurringIntention calls delete endpoint", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/recurring/intent-123"
      );
      assert.strictEqual(init?.method, "DELETE");
      return new Response(JSON.stringify({ message: "Deleted" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.deleteRecurringIntention("intent-123");
    assert.strictEqual(res.message, "Deleted");
  });

  await t.test("clearAllIntentMemories deletes all customer intent data", async () => {
    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/clear-all"
      );
      assert.strictEqual(init?.method, "DELETE");
      return new Response(
        JSON.stringify({ message: "All shopping memories cleared successfully." }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await apiClient.clearAllIntentMemories();
    assert.ok(res.message.includes("cleared"));
  });

  await t.test("getIntentSuggestions returns suggestions with category filter", async () => {
    const mockSuggestions: IntentSuggestionResponse = {
      suggested_brands: ["Sony", "Apple"],
      suggested_priorities: ["QUALITY"],
      suggested_budget_paise: 500000,
      suggested_categories: ["cat-audio"],
      applicable_intentions: [mockIntention],
      personalization_enabled: true,
      explanation: "Suggested based on your saved shopping preferences.",
    };

    globalThis.fetch = async (input, init) => {
      assert.strictEqual(
        String(input),
        "http://localhost:8000/api/v1/intent/suggestions?category_id=cat-audio"
      );
      assert.strictEqual(init?.method, "GET");
      return new Response(JSON.stringify(mockSuggestions), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getIntentSuggestions("cat-audio");
    assert.strictEqual(res.suggested_brands.length, 2);
    assert.strictEqual(res.suggested_brands[0], "Sony");
    assert.strictEqual(res.applicable_intentions.length, 1);
  });
});
