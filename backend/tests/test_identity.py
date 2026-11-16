import asyncio
import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.database import get_session_factory
from app.core.exceptions import AppException
from app.modules.identity.models import User
from app.modules.identity.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    login_rate_limiter,
    verify_password,
)


@pytest.fixture(autouse=True)
async def reset_login_limiter():
    """Ensure rate limiter state is reset between tests."""
    await login_rate_limiter.reset()
    yield
    await login_rate_limiter.reset()


def test_password_hashing_argon2id():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    # Verify Argon2id prefix and configuration
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_access_token_creation_and_validation():
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="customer")
    decoded = decode_access_token(token)

    assert decoded["sub"] == str(user_id)
    assert decoded["role"] == "customer"
    assert decoded["token_use"] == "access"


def test_jwt_expired_token():
    user_id = uuid.uuid4()
    expired_delta = datetime.timedelta(seconds=-10)
    token = create_access_token(user_id=user_id, expires_delta=expired_delta)

    with pytest.raises(AppException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == "TOKEN_EXPIRED"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": f"  {unique_email.upper()}  ",  # Test normalization
        "password": "SecurePassword123!",
        "full_name": "Priya Sharma",
        "phone": "+919876543210",
    }

    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["user"]["email"] == unique_email
    assert data["user"]["full_name"] == "Priya Sharma"
    assert data["user"]["role"] == "customer"
    assert data["user"]["is_active"] is True
    assert "access_token" in data
    assert "refresh_token" in data
    assert "csrf_token" in data

    # Check cookies set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert "XSRF-TOKEN" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "SecurePassword123!",
        "full_name": "Rahul Verma",
    }

    # First registration
    resp1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Second registration with same email
    resp2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_register_validation_errors(async_client: AsyncClient):
    # Invalid email
    resp_invalid_email = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "full_name": "Test User",
        },
    )
    assert resp_invalid_email.status_code == 422

    # Short password
    resp_short_pw = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@example.com",
            "password": "short",
            "full_name": "Test User",
        },
    )
    assert resp_short_pw.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    password = "MyPassword123!"

    # Register
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Aarav Patel"},
    )

    # Login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": password},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["email"] == email
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient):
    email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Aarav Patel"},
    )

    # Login with incorrect password
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword123!"},
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_rate_limiting(async_client: AsyncClient):
    email = "ratelimit_victim@example.com"

    # Rapidly fail 5 times
    for _ in range(5):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "BadPassword123!"},
        )
        assert resp.status_code == 401

    # 6th attempt should be blocked by rate limiter
    blocked_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BadPassword123!"},
    )
    assert blocked_resp.status_code == 429
    assert blocked_resp.json()["error"]["code"] == "LOGIN_RATE_LIMITED"


@pytest.mark.asyncio
async def test_user_me_endpoint(async_client: AsyncClient):
    email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Me Profile",
        },
    )
    token = reg_resp.json()["access_token"]

    # 1. Bearer token in Authorization header
    me_resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 2. Cookie authentication
    async_client.cookies.set("access_token", token)
    me_cookie_resp = await async_client.get("/api/v1/users/me")
    assert me_cookie_resp.status_code == 200
    assert me_cookie_resp.json()["email"] == email

    # 3. Unauthenticated request
    async_client.cookies.clear()
    unauth_resp = await async_client.get("/api/v1/users/me")
    assert unauth_resp.status_code == 401
    assert unauth_resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_refresh_token_rotation(async_client: AsyncClient):
    email = f"rotate_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Rotate User",
        },
    )
    refresh_token_1 = reg_resp.json()["refresh_token"]

    # First rotation
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    refresh_token_2 = data["refresh_token"]
    assert refresh_token_2 != refresh_token_1
    assert "access_token" in data

    # Verify new access token works
    me_resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token_replay_attack_detection(async_client: AsyncClient):
    email = f"replay_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Replay User",
        },
    )
    refresh_token_1 = reg_resp.json()["refresh_token"]

    # Legitimate rotation
    refresh_resp_1 = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert refresh_resp_1.status_code == 200
    refresh_token_2 = refresh_resp_1.json()["refresh_token"]

    # Attacker tries to replay the old refresh_token_1!
    replay_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert replay_resp.status_code == 401
    assert replay_resp.json()["error"]["code"] == "TOKEN_REVOKED"

    # Family invalidation check: Even the legitimate refresh_token_2 is now revoked!
    refresh_resp_2 = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert refresh_resp_2.status_code == 401
    assert refresh_resp_2.json()["error"]["code"] == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_logout_invalidation(async_client: AsyncClient):
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Logout User",
        },
    )
    refresh_token = reg_resp.json()["refresh_token"]
    csrf_token = reg_resp.json()["csrf_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_resp.status_code == 200

    # Refresh with revoked token must fail
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_sessions(async_client: AsyncClient):
    email = f"logoutall_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"

    # Session 1: Register
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Multi Device"},
    )
    refresh_1 = reg_resp.json()["refresh_token"]

    # Session 2: Login on second device (updates cookies on async_client to session 2)
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    refresh_2 = login_resp.json()["refresh_token"]
    access_2 = login_resp.json()["access_token"]
    csrf_2 = login_resp.json()["csrf_token"]

    # Terminate all sessions from session 2
    logout_all_resp = await async_client.post(
        "/api/v1/auth/logout-all",
        headers={
            "Authorization": f"Bearer {access_2}",
            "X-CSRF-Token": csrf_2,
        },
    )
    assert logout_all_resp.status_code == 200

    # Both refresh tokens must now be rejected
    ref1_fail = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_1}
    )
    assert ref1_fail.status_code == 401

    ref2_fail = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_2}
    )
    assert ref2_fail.status_code == 401


@pytest.mark.asyncio
async def test_csrf_protection_on_cookie_auth(async_client: AsyncClient):
    email = f"csrf_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "CSRF Test"},
    )
    csrf_token = reg_resp.json()["csrf_token"]
    access_token = reg_resp.json()["access_token"]

    # Set access_token cookie
    async_client.cookies.set("access_token", access_token)
    async_client.cookies.set("XSRF-TOKEN", csrf_token)

    # 1. State-mutating request without CSRF header -> 403 CSRF_TOKEN_MISSING
    resp_missing = await async_client.post("/api/v1/auth/logout", json={})
    assert resp_missing.status_code == 403
    assert resp_missing.json()["error"]["code"] == "CSRF_TOKEN_MISSING"

    # 2. State-mutating request with wrong CSRF header -> 403 CSRF_TOKEN_INVALID
    resp_wrong = await async_client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"X-CSRF-Token": "tampered-token"},
    )
    assert resp_wrong.status_code == 403
    assert resp_wrong.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    # 3. State-mutating request with matching CSRF header -> 200 OK
    resp_valid = await async_client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_valid.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_refresh_requests(async_client: AsyncClient):
    email = f"concurrent_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Concurrent User",
        },
    )
    refresh_token = reg_resp.json()["refresh_token"]

    # Fire two concurrent refresh requests using the exact same refresh token
    responses = await asyncio.gather(
        async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        ),
        async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        ),
        return_exceptions=False,
    )
    status_codes = [r.status_code for r in responses]
    # Exactly one request must succeed (200), and the other must be rejected (401)
    assert 200 in status_codes
    assert 401 in status_codes
    err_resp = next(r for r in responses if r.status_code == 401)
    assert err_resp.json()["error"]["code"] in (
        "INVALID_REFRESH_TOKEN",
        "TOKEN_REVOKED",
    )

    # Confirm replay detection revokes the entire token family
    success_resp = next(r for r in responses if r.status_code == 200)
    new_token = success_resp.json()["refresh_token"]

    # Replaying the old token must trigger replay attack detection
    replay_resp = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert replay_resp.status_code == 401
    assert replay_resp.json()["error"]["code"] == "TOKEN_REVOKED"

    # The newly minted token from the successful request must now also be revoked
    revoked_new_resp = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_token}
    )
    assert revoked_new_resp.status_code == 401
    assert revoked_new_resp.json()["error"]["code"] == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_instant_access_token_revocation_on_logout(
    async_client: AsyncClient,
):
    email = f"instant_rev_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Instant Revoke",
        },
    )
    access_token = reg_resp.json()["access_token"]
    refresh_token = reg_resp.json()["refresh_token"]
    csrf_token = reg_resp.json()["csrf_token"]

    # Verify access token works initially
    me_resp_before = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp_before.status_code == 200

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_resp.status_code == 200

    # Access token must now be instantly rejected because session is revoked in database
    me_resp_after = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp_after.status_code == 401
    assert me_resp_after.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_auth_cookie_attributes(async_client: AsyncClient):
    email = f"cookies_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Cookie Test",
        },
    )
    assert reg_resp.status_code == 201

    raw_cookies = reg_resp.headers.get_list("set-cookie")

    # 1. access_token: HttpOnly, Path=/
    access_cookie = next(c for c in raw_cookies if c.startswith("access_token="))
    assert "HttpOnly" in access_cookie
    assert "Path=/" in access_cookie
    assert "samesite=lax" in access_cookie.lower()

    # 2. refresh_token: HttpOnly, Path=/api/v1/auth, SameSite=Strict
    refresh_cookie = next(c for c in raw_cookies if c.startswith("refresh_token="))
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie
    assert "samesite=strict" in refresh_cookie.lower()

    # 3. XSRF-TOKEN: not HttpOnly (must be readable by JS for double-submit)
    xsrf_cookie = next(c for c in raw_cookies if c.startswith("XSRF-TOKEN="))
    assert "HttpOnly" not in xsrf_cookie
    assert "Path=/" in xsrf_cookie


@pytest.mark.asyncio
async def test_csrf_origin_validation(async_client: AsyncClient):
    email = f"csrf_origin_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "CSRF Origin",
        },
    )
    csrf_token = reg_resp.json()["csrf_token"]
    access_token = reg_resp.json()["access_token"]

    async_client.cookies.set("access_token", access_token)
    async_client.cookies.set("XSRF-TOKEN", csrf_token)

    # Untrusted origin -> 403 CSRF_ORIGIN_INVALID
    resp = await async_client.post(
        "/api/v1/auth/logout",
        json={},
        headers={
            "X-CSRF-Token": csrf_token,
            "Origin": "https://malicious-phishing-site.com",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_INVALID"


@pytest.mark.asyncio
async def test_role_escalation_prevention(async_client: AsyncClient):
    email = f"escalate_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Attacker",
            "role": "admin",  # Attempt to inject admin role
        },
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["user"]["role"] == "customer"


@pytest.mark.asyncio
async def test_inactive_account_blocked(async_client: AsyncClient):
    email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Deactivated User",
        },
    )
    access_token = reg_resp.json()["access_token"]
    refresh_token = reg_resp.json()["refresh_token"]

    # Deactivate user in database
    session_factory = get_session_factory()
    assert session_factory is not None
    async with session_factory() as session:
        await session.execute(
            update(User).where(User.email == email).values(is_active=False)
        )
        await session.commit()

    # 1. Login must fail with 401
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # 2. Access to /users/me must fail with 403
    me_resp = await async_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 403
    assert me_resp.json()["error"]["code"] == "USER_INACTIVE"

    # 3. Token refresh must fail with 403
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 403
    assert refresh_resp.json()["error"]["code"] == "USER_INACTIVE"


@pytest.mark.asyncio
async def test_address_lifecycle_and_default_constraints(
    async_client: AsyncClient,
):
    email = f"address_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Address Owner",
        },
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Initially zero addresses
    list_0 = await async_client.get("/api/v1/addresses", headers=headers)
    assert list_0.status_code == 200
    assert list_0.json() == []

    # 1. First address: auto-promoted to is_default=True even if passed False
    addr1_payload = {
        "recipient_name": "Aarav Patel",
        "phone": "+919876543210",
        "line1": "Flat 402, Sunshine Heights",
        "line2": "MG Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560001",
        "landmark": "Near Metro Station",
        "is_default": False,
    }
    resp1 = await async_client.post(
        "/api/v1/addresses", json=addr1_payload, headers=headers
    )
    assert resp1.status_code == 201
    addr1 = resp1.json()
    assert addr1["is_default"] is True  # Auto-default enforced for first address

    # 2. Second address with is_default=False: addr1 remains default
    addr2_payload = {
        "recipient_name": "Aarav Office",
        "phone": "+919876543210",
        "line1": "Tech Park, Building 3",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560103",
        "is_default": False,
    }
    resp2 = await async_client.post(
        "/api/v1/addresses", json=addr2_payload, headers=headers
    )
    assert resp2.status_code == 201
    addr2 = resp2.json()
    assert addr2["is_default"] is False

    # 3. Third address with is_default=True: becomes default, unsets addr1
    addr3_payload = {
        "recipient_name": "Aarav Parents",
        "phone": "+919876543210",
        "line1": "12 Gandhi Marg",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "is_default": True,
    }
    resp3 = await async_client.post(
        "/api/v1/addresses", json=addr3_payload, headers=headers
    )
    assert resp3.status_code == 201
    addr3 = resp3.json()
    assert addr3["is_default"] is True

    # Verify list order: default address (addr3) first, followed by others
    list_all = await async_client.get("/api/v1/addresses", headers=headers)
    items = list_all.json()
    assert len(items) == 3
    assert items[0]["id"] == addr3["id"]
    assert items[0]["is_default"] is True
    assert items[1]["is_default"] is False
    assert items[2]["is_default"] is False

    # 4. Patch addr2 to become default
    patch_resp = await async_client.patch(
        f"/api/v1/addresses/{addr2['id']}",
        json={"is_default": True, "recipient_name": "Aarav Primary Office"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_default"] is True
    assert patch_resp.json()["recipient_name"] == "Aarav Primary Office"

    # Verify addr3 is no longer default
    list_after_patch = await async_client.get("/api/v1/addresses", headers=headers)
    defaults = [a for a in list_after_patch.json() if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == addr2["id"]

    # 5. Delete default address (addr2): oldest remaining address (addr1) is auto-promoted
    del_resp = await async_client.delete(
        f"/api/v1/addresses/{addr2['id']}", headers=headers
    )
    assert del_resp.status_code == 200

    list_after_del = await async_client.get("/api/v1/addresses", headers=headers)
    remaining = list_after_del.json()
    assert len(remaining) == 2
    defaults_now = [a for a in remaining if a["is_default"]]
    assert len(defaults_now) == 1
    assert defaults_now[0]["id"] == addr1["id"]

    # 6. Delete remaining addresses until zero
    await async_client.delete(f"/api/v1/addresses/{addr1['id']}", headers=headers)
    await async_client.delete(f"/api/v1/addresses/{addr3['id']}", headers=headers)

    list_empty = await async_client.get("/api/v1/addresses", headers=headers)
    assert list_empty.json() == []


@pytest.mark.asyncio
async def test_address_customer_isolation(async_client: AsyncClient):
    # Customer A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"usera_{uuid.uuid4().hex[:8]}@example.com",
            "password": "Password123!",
            "full_name": "User A",
        },
    )
    token_a = reg_a.json()["access_token"]

    # Customer B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"userb_{uuid.uuid4().hex[:8]}@example.com",
            "password": "Password123!",
            "full_name": "User B",
        },
    )
    token_b = reg_b.json()["access_token"]

    # User A creates an address
    addr_resp = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "User A Address",
            "phone": "+919876543210",
            "line1": "Secret Location A",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    addr_id = addr_resp.json()["id"]

    # User B attempts to PATCH User A's address -> 404
    patch_resp = await async_client.patch(
        f"/api/v1/addresses/{addr_id}",
        json={"recipient_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert patch_resp.status_code == 404
    assert patch_resp.json()["error"]["code"] == "ADDRESS_NOT_FOUND"

    # User B attempts to DELETE User A's address -> 404
    del_resp = await async_client.delete(
        f"/api/v1/addresses/{addr_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["error"]["code"] == "ADDRESS_NOT_FOUND"


@pytest.mark.asyncio
async def test_address_pin_code_validation(async_client: AsyncClient):
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"pin_{uuid.uuid4().hex[:8]}@example.com",
            "password": "Password123!",
            "full_name": "PIN Test",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 5 digits -> 422
    r1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Test",
            "phone": "+919876543210",
            "line1": "Street",
            "city": "Delhi",
            "state": "Delhi",
            "postal_code": "11001",
        },
        headers=headers,
    )
    assert r1.status_code == 422

    # Starting with 0 -> 422
    r2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Test",
            "phone": "+919876543210",
            "line1": "Street",
            "city": "Delhi",
            "state": "Delhi",
            "postal_code": "010012",
        },
        headers=headers,
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_address_default_updates(async_client: AsyncClient):
    """Simulate simultaneous requests setting different addresses as default."""
    email = f"addr_concurrent_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Concurrent Address User",
        },
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Address 1 (auto-default)
    r1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Addr 1",
            "phone": "+919876543210",
            "line1": "Street 1",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
        },
        headers=headers,
    )
    addr1_id = r1.json()["id"]

    # Create Address 2
    r2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Addr 2",
            "phone": "+919876543210",
            "line1": "Street 2",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560002",
        },
        headers=headers,
    )
    addr2_id = r2.json()["id"]

    # Create Address 3
    r3 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Addr 3",
            "phone": "+919876543210",
            "line1": "Street 3",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560003",
        },
        headers=headers,
    )
    addr3_id = r3.json()["id"]

    # Concurrently request setting addr2 and addr3 as default
    responses = await asyncio.gather(
        async_client.patch(
            f"/api/v1/addresses/{addr2_id}",
            json={"is_default": True},
            headers=headers,
        ),
        async_client.patch(
            f"/api/v1/addresses/{addr3_id}",
            json={"is_default": True},
            headers=headers,
        ),
        return_exceptions=False,
    )
    # Both requests must succeed (serialized via user row lock)
    assert responses[0].status_code == 200
    assert responses[1].status_code == 200

    # Verify at-most-one-default database constraint: exactly 1 address is default
    list_resp = await async_client.get("/api/v1/addresses", headers=headers)
    addresses = list_resp.json()
    defaults = [a for a in addresses if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] in (addr2_id, addr3_id)
    assert defaults[0]["id"] != addr1_id


@pytest.mark.asyncio
async def test_concurrent_address_deletion_and_promotion(
    async_client: AsyncClient,
):
    """Test concurrent default-address deletion and fallback promotion."""
    email = f"addr_del_concurrent_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Deletion User",
        },
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Address 1 (auto-default)
    r1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Oldest",
            "phone": "+919876543210",
            "line1": "Line 1",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
        },
        headers=headers,
    )
    addr1_id = r1.json()["id"]

    # Create Address 2
    r2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Second Oldest",
            "phone": "+919876543210",
            "line1": "Line 2",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560002",
        },
        headers=headers,
    )
    addr2_id = r2.json()["id"]

    # Create Address 3 (set as default)
    r3 = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Current Default",
            "phone": "+919876543210",
            "line1": "Line 3",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560003",
            "is_default": True,
        },
        headers=headers,
    )
    addr3_id = r3.json()["id"]

    # Concurrently attempt to delete the default address addr3 twice
    responses = await asyncio.gather(
        async_client.delete(f"/api/v1/addresses/{addr3_id}", headers=headers),
        async_client.delete(f"/api/v1/addresses/{addr3_id}", headers=headers),
        return_exceptions=False,
    )
    status_codes = [r.status_code for r in responses]
    # One succeeds (200), the other gets 404 ADDRESS_NOT_FOUND
    assert 200 in status_codes
    assert 404 in status_codes

    # Verify fallback promotion: exactly one remaining address is default (addr1, the oldest)
    list_resp = await async_client.get("/api/v1/addresses", headers=headers)
    remaining = list_resp.json()
    assert len(remaining) == 2
    remaining_ids = [a["id"] for a in remaining]
    assert addr1_id in remaining_ids
    assert addr2_id in remaining_ids
    defaults = [a for a in remaining if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == addr1_id
