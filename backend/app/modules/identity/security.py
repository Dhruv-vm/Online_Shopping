import asyncio
import datetime
import hashlib
import secrets
import time
import uuid
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from starlette.responses import Response

from app.core.config import settings
from app.core.exceptions import AppException

# Argon2id password hasher with parameters specified in Phase 2 Architecture:
# memory_cost=64MB (65536 KB), time_cost=3 iterations, parallelism=4 threads
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def normalize_email(email: str) -> str:
    """Normalize email address by stripping whitespace and lowercasing."""
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def generate_refresh_token() -> str:
    """Generate a high-entropy cryptographically secure refresh token."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token string for safe database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def create_access_token(
    user_id: uuid.UUID,
    role: str = "customer",
    session_id: uuid.UUID | None = None,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """Create a signed JWT access token with user claims, session pointer, and expiration."""
    now = datetime.datetime.now(datetime.UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "token_use": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    if session_id:
        payload["sid"] = str(session_id)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("token_use") != "access":
            raise AppException(
                code="INVALID_TOKEN",
                message="Invalid token use type.",
                status_code=401,
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException(
            code="TOKEN_EXPIRED",
            message="Access token has expired.",
            status_code=401,
        ) from None
    except jwt.InvalidTokenError:
        raise AppException(
            code="INVALID_TOKEN",
            message="Could not validate credentials.",
            status_code=401,
        ) from None


class LoginRateLimiter:
    """Sliding-window in-memory login rate limiter with exponential lockout.

    Rules:
    - Max 5 failed attempts per 60 seconds per (ip, email).
    - 10 failures triggers a 15-minute lockout (900 seconds).
    """

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    def _key(self, ip: str, email: str) -> str:
        return f"{ip}:{email}"

    async def check_rate_limit(self, ip: str, email: str) -> None:
        async with self._lock:
            key = self._key(ip, email)
            now = time.time()
            timestamps = self._failures.get(key, [])

            # Purge timestamps older than 15 minutes (900 seconds)
            timestamps = [t for t in timestamps if now - t < 900]
            self._failures[key] = timestamps

            if len(timestamps) >= 10:
                oldest_in_window = timestamps[-10]
                remaining_lockout = int(900 - (now - oldest_in_window))
                if remaining_lockout > 0:
                    raise AppException(
                        code="LOGIN_RATE_LIMITED",
                        message=f"Too many failed login attempts. Account temporarily locked. Try again in {remaining_lockout} seconds.",
                        status_code=429,
                        details=[{"retry_after": remaining_lockout}],
                    )

            # Check 60-second window for 5 attempts
            recent_attempts = [t for t in timestamps if now - t < 60]
            if len(recent_attempts) >= 5:
                retry_after = int(60 - (now - recent_attempts[0]))
                if retry_after > 0:
                    raise AppException(
                        code="LOGIN_RATE_LIMITED",
                        message=f"Too many login attempts. Please wait {retry_after} seconds.",
                        status_code=429,
                        details=[{"retry_after": retry_after}],
                    )

    async def record_failure(self, ip: str, email: str) -> None:
        async with self._lock:
            key = self._key(ip, email)
            now = time.time()
            if key not in self._failures:
                self._failures[key] = []
            self._failures[key].append(now)

    async def record_success(self, ip: str, email: str) -> None:
        async with self._lock:
            key = self._key(ip, email)
            self._failures.pop(key, None)

    async def reset(self) -> None:
        """Helper for test suites to clear all rate limit state."""
        async with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str | None = None,
) -> None:
    """Set secure HTTP-only cookies for authentication."""
    # Access token cookie (15 mins)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    # Refresh token cookie (7 days)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/api/v1/auth",
    )

    # CSRF cookie (accessible to JavaScript for X-CSRF-Token double submit)
    if csrf_token:
        response.set_cookie(
            key="XSRF-TOKEN",
            value=csrf_token,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            httponly=False,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication and session cookies."""
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )
    response.delete_cookie(
        key="XSRF-TOKEN",
        path="/",
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
