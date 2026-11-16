import test from "node:test";
import assert from "node:assert/strict";
import { apiClient, ApiClientError } from "./client.ts";
import type { User, AuthResponse, Address } from "@/types";

test("Authentication and Address API Client integration", async (t) => {
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  // 1. Registration flow
  await t.test("register() posts customer details and returns AuthResponse", async () => {
    let capturedUrl: string | undefined;
    let capturedBody: string | undefined;
    let capturedCredentials: RequestCredentials | undefined;

    const mockResponse: AuthResponse = {
      user: {
        id: "user-123",
        email: "priya@example.com",
        phone: "+919876543210",
        full_name: "Priya Sharma",
        role: "customer",
        is_active: true,
        created_at: "2026-11-16T12:00:00Z",
      },
      access_token: "mock-jwt-access-token",
      refresh_token: "mock-refresh-token",
      csrf_token: "mock-csrf-token",
      token_type: "bearer",
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedBody = init?.body as string;
      capturedCredentials = init?.credentials;
      return new Response(JSON.stringify(mockResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.register({
      full_name: "Priya Sharma",
      email: "priya@example.com",
      password: "SecurePassword123!",
      phone: "+919876543210",
    });

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/auth/register");
    assert.equal(capturedCredentials, "include");
    assert.deepEqual(JSON.parse(capturedBody || "{}"), {
      full_name: "Priya Sharma",
      email: "priya@example.com",
      password: "SecurePassword123!",
      phone: "+919876543210",
    });
    assert.equal(res.user.email, "priya@example.com");
    assert.equal(res.user.role, "customer");
  });

  // 2. Login flow
  await t.test("login() posts credentials and includes credentials cookie mode", async () => {
    let capturedUrl: string | undefined;
    let capturedCredentials: RequestCredentials | undefined;

    const mockResponse: AuthResponse = {
      user: {
        id: "user-456",
        email: "rahul@example.com",
        full_name: "Rahul Verma",
        role: "customer",
        is_active: true,
        created_at: "2026-11-16T12:00:00Z",
      },
      access_token: "mock-jwt-token",
      refresh_token: "mock-refresh",
      csrf_token: "mock-csrf",
      token_type: "bearer",
    };

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedCredentials = init?.credentials;
      return new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.login({
      email: "rahul@example.com",
      password: "MyPassword123!",
    });

    assert.equal(capturedUrl, "http://localhost:8000/api/v1/auth/login");
    assert.equal(capturedCredentials, "include");
    assert.equal(res.user.full_name, "Rahul Verma");
  });

  // 3. Invalid credentials handling (401)
  await t.test("login() with invalid credentials throws ApiClientError 401", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Invalid email or password.",
          },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );

    await assert.rejects(
      async () => {
        await apiClient.login({ email: "wrong@example.com", password: "bad" });
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 401);
        assert.equal(err.code, "INVALID_CREDENTIALS");
        assert.equal(err.message, "Invalid email or password.");
        return true;
      }
    );
  });

  // 4. Rate limiting handling (429)
  await t.test("login() rate limiting throws ApiClientError 429", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "LOGIN_RATE_LIMITED",
            message: "Too many failed login attempts. Try again in 60s.",
          },
        }),
        { status: 429, headers: { "Content-Type": "application/json" } }
      );

    await assert.rejects(
      async () => {
        await apiClient.login({ email: "victim@example.com", password: "bad" });
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 429);
        assert.equal(err.code, "LOGIN_RATE_LIMITED");
        return true;
      }
    );
  });

  // 5. Logout & Logout-all
  await t.test("logout() and logoutAll() call appropriate auth endpoints", async () => {
    const urlsCalled: string[] = [];

    globalThis.fetch = async (input) => {
      urlsCalled.push(input.toString());
      return new Response(JSON.stringify({ message: "Successfully logged out." }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await apiClient.logout();
    await apiClient.logoutAll();

    assert.equal(urlsCalled[0], "http://localhost:8000/api/v1/auth/logout");
    assert.equal(urlsCalled[1], "http://localhost:8000/api/v1/auth/logout-all");
  });

  // 6. Profile / Authentication State
  await t.test("getProfile() fetches current user profile from /api/v1/users/me", async () => {
    const mockUser: User = {
      id: "user-789",
      email: "user@example.com",
      full_name: "Test User",
      role: "customer",
      is_active: true,
      created_at: "2026-11-16T12:00:00Z",
    };

    globalThis.fetch = async (input) => {
      assert.equal(input.toString(), "http://localhost:8000/api/v1/users/me");
      return new Response(JSON.stringify(mockUser), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const user = await apiClient.getProfile();
    assert.deepEqual(user, mockUser);
  });

  // 7. CSRF Handling on state mutations
  await t.test("CSRF header is attached when XSRF-TOKEN cookie exists in document", async () => {
    let capturedCsrfHeader: string | undefined;

    // Simulate browser document.cookie
    const originalDocument = globalThis.document;
    // @ts-expect-error Mock document for node environment test
    globalThis.document = {
      cookie: "XSRF-TOKEN=test-csrf-token-12345; other_cookie=xyz",
    };

    try {
      globalThis.fetch = async (input, init) => {
        const headers = init?.headers as Record<string, string>;
        capturedCsrfHeader = headers?.["X-CSRF-Token"];
        return new Response(JSON.stringify({ message: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      };

      await apiClient.post("/api/v1/test-mutation", { data: 1 });
      assert.equal(capturedCsrfHeader, "test-csrf-token-12345");
    } finally {
      globalThis.document = originalDocument;
    }
  });

  // 8. Session Expiry & Token Refresh
  await t.test("automatic token refresh retries original request upon 401", async () => {
    let attempts = 0;
    let refreshCalls = 0;

    globalThis.fetch = async (input) => {
      const url = input.toString();

      if (url.includes("/api/v1/auth/refresh")) {
        refreshCalls++;
        return new Response(
          JSON.stringify({
            access_token: "new-access",
            refresh_token: "new-refresh",
            csrf_token: "new-csrf",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/users/me")) {
        attempts++;
        if (attempts === 1) {
          // First attempt fails with 401 TOKEN_EXPIRED
          return new Response(
            JSON.stringify({
              error: { code: "TOKEN_EXPIRED", message: "Token expired" },
            }),
            { status: 401, headers: { "Content-Type": "application/json" } }
          );
        }
        // Second attempt succeeds
        return new Response(
          JSON.stringify({
            id: "user-123",
            email: "refreshed@example.com",
            full_name: "Refreshed User",
            role: "customer",
            is_active: true,
            created_at: "2026-11-16T12:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response("Not Found", { status: 404 });
    };

    const user = await apiClient.getProfile();
    assert.equal(user.email, "refreshed@example.com");
    assert.equal(refreshCalls, 1);
    assert.equal(attempts, 2);
  });

  // 9. Avoid duplicate requests during concurrent token refresh
  await t.test("concurrent requests share single-flight token refresh", async () => {
    let refreshCalls = 0;
    let profileCalls = 0;

    globalThis.fetch = async (input) => {
      const url = input.toString();

      if (url.includes("/api/v1/auth/refresh")) {
        refreshCalls++;
        // Simulate minor async delay
        await new Promise((r) => setTimeout(r, 10));
        return new Response(
          JSON.stringify({
            access_token: "new-access",
            refresh_token: "new-refresh",
            csrf_token: "new-csrf",
            token_type: "bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/api/v1/users/me")) {
        profileCalls++;
        // If first two calls before refresh completes, return 401
        if (refreshCalls === 0) {
          return new Response(
            JSON.stringify({
              error: { code: "TOKEN_EXPIRED", message: "Token expired" },
            }),
            { status: 401, headers: { "Content-Type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({
            id: "u-1",
            email: "concurrent@example.com",
            full_name: "Concurrent",
            role: "customer",
            is_active: true,
            created_at: "2026-11-16T12:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response("Not Found", { status: 404 });
    };

    // Dispatch two concurrent profile requests
    const [u1, u2] = await Promise.all([
      apiClient.getProfile(),
      apiClient.getProfile(),
    ]);

    assert.equal(u1.email, "concurrent@example.com");
    assert.equal(u2.email, "concurrent@example.com");
    // Exactly ONE refresh request must be executed
    assert.equal(refreshCalls, 1);
  });

  // 10. Address CRUD & Default Selection
  await t.test("getAddresses() fetches customer addresses list", async () => {
    const mockAddresses: Address[] = [
      {
        id: "addr-1",
        user_id: "user-123",
        recipient_name: "Priya Sharma",
        phone: "+919876543210",
        line1: "Flat 402, Sunshine Heights",
        city: "Bengaluru",
        state: "Karnataka",
        postal_code: "560001",
        is_default: true,
        created_at: "2026-11-16T12:00:00Z",
      },
    ];

    globalThis.fetch = async (input) => {
      assert.equal(input.toString(), "http://localhost:8000/api/v1/addresses");
      return new Response(JSON.stringify(mockAddresses), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.getAddresses();
    assert.equal(res.length, 1);
    assert.equal(res[0].is_default, true);
    assert.equal(res[0].postal_code, "560001");
  });

  await t.test("createAddress() posts new address payload", async () => {
    let capturedBody: string | undefined;

    const mockCreated: Address = {
      id: "addr-2",
      user_id: "user-123",
      recipient_name: "Rahul Verma",
      phone: "+919876543210",
      line1: "12 Gandhi Marg",
      city: "Mumbai",
      state: "Maharashtra",
      postal_code: "400001",
      is_default: false,
      created_at: "2026-11-16T12:00:00Z",
    };

    globalThis.fetch = async (input, init) => {
      capturedBody = init?.body as string;
      return new Response(JSON.stringify(mockCreated), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await apiClient.createAddress({
      recipient_name: "Rahul Verma",
      phone: "+919876543210",
      line1: "12 Gandhi Marg",
      city: "Mumbai",
      state: "Maharashtra",
      postal_code: "400001",
      is_default: false,
    });

    assert.equal(res.id, "addr-2");
    assert.equal(res.city, "Mumbai");
    assert.equal(JSON.parse(capturedBody || "{}").postal_code, "400001");
  });

  await t.test("updateAddress() sends PATCH with default address toggle", async () => {
    let capturedMethod: string | undefined;
    let capturedUrl: string | undefined;
    let capturedBody: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(
        JSON.stringify({
          id: "addr-2",
          user_id: "user-123",
          recipient_name: "Rahul Verma",
          phone: "+919876543210",
          line1: "12 Gandhi Marg",
          city: "Mumbai",
          state: "Maharashtra",
          postal_code: "400001",
          is_default: true,
          created_at: "2026-11-16T12:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await apiClient.updateAddress("addr-2", { is_default: true });
    assert.equal(capturedMethod, "PATCH");
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/addresses/addr-2");
    assert.equal(JSON.parse(capturedBody || "{}").is_default, true);
    assert.equal(res.is_default, true);
  });

  await t.test("deleteAddress() sends DELETE request", async () => {
    let capturedMethod: string | undefined;
    let capturedUrl: string | undefined;

    globalThis.fetch = async (input, init) => {
      capturedUrl = input.toString();
      capturedMethod = init?.method;
      return new Response(
        JSON.stringify({ message: "Address deleted successfully." }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await apiClient.deleteAddress("addr-2");
    assert.equal(capturedMethod, "DELETE");
    assert.equal(capturedUrl, "http://localhost:8000/api/v1/addresses/addr-2");
    assert.equal(res.message, "Address deleted successfully.");
  });

  // 11. Address ownership error response
  await t.test("address ownership violation throws ApiClientError 404", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "ADDRESS_NOT_FOUND",
            message: "Address not found.",
          },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );

    await assert.rejects(
      async () => {
        await apiClient.deleteAddress("unauthorized-address-id");
      },
      (err: unknown) => {
        assert(err instanceof ApiClientError);
        assert.equal(err.status, 404);
        assert.equal(err.code, "ADDRESS_NOT_FOUND");
        return true;
      }
    );
  });
});
