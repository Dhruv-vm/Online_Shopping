import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";

test("ApiClient methods and error handling", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  await t.test("get() returns parsed json response", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ message: "success" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });

    const res = await apiClient.get<{ message: string }>("/test");
    assert.deepEqual(res, { message: "success" });
  });

  await t.test("post() sends serialized body and parses json", async () => {
    let capturedBody: string | undefined;
    let capturedMethod: string | undefined;

    globalThis.fetch = async (url, init) => {
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify({ id: "123" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.post<{ id: string }>("/items", { name: "apple" });
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody, JSON.stringify({ name: "apple" }));
    assert.deepEqual(res, { id: "123" });
  });

  await t.test("patch() sends PATCH method and serialized body", async () => {
    let capturedMethod: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (url, init) => {
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify({ id: "123", quantity: 5 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.patch<{ id: string; quantity: number }>("/cart/items/123", {
      quantity: 5,
    });
    assert.equal(capturedMethod, "PATCH");
    assert.equal(capturedBody, JSON.stringify({ quantity: 5 }));
    assert.deepEqual(res, { id: "123", quantity: 5 });
  });

  await t.test("delete() supports HTTP 204 No Content with undefined return", async () => {
    let capturedMethod: string | undefined;

    globalThis.fetch = async (url, init) => {
      capturedMethod = init?.method;
      return new Response(null, {
        status: 204,
      });
    };

    const res = await apiClient.delete("/cart/items/123");
    assert.equal(capturedMethod, "DELETE");
    assert.equal(res, undefined);
  });

  await t.test("delete() supports HTTP 200 with response body", async () => {
    let capturedMethod: string | undefined;

    globalThis.fetch = async (url, init) => {
      capturedMethod = init?.method;
      return new Response(JSON.stringify({ removed: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.delete<{ removed: boolean }>("/cart/items/123");
    assert.equal(capturedMethod, "DELETE");
    assert.deepEqual(res, { removed: true });
  });

  await t.test("throws structured ApiClientError on API error envelope", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "NOT_FOUND",
            message: "Item not found",
            request_id: "req-123",
          },
        }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }
      );

    await assert.rejects(
      async () => {
        await apiClient.get("/items/999");
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 404);
        assert.equal(err.code, "NOT_FOUND");
        assert.equal(err.requestId, "req-123");
        assert.equal(err.message, "Item not found");
        return true;
      }
    );
  });
});
