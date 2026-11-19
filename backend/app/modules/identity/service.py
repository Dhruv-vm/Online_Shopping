import datetime
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.modules.identity.models import Address, User, UserSession
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import (
    AddressCreateRequest,
    AddressUpdateRequest,
    RetailerRegisterRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.identity.security import (
    create_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    login_rate_limiter,
    normalize_email,
    verify_password,
)


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = IdentityRepository(session)

    async def register(
        self,
        request: UserRegisterRequest,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str, str]:
        normalized_email = normalize_email(request.email)

        existing_user = await self.repo.get_user_by_email(normalized_email)
        if existing_user:
            raise AppException(
                code="EMAIL_ALREADY_EXISTS",
                message="An account with this email already exists.",
                status_code=409,
            )

        hashed = hash_password(request.password)
        user = User(
            email=normalized_email,
            phone=request.phone.strip() if request.phone else None,
            full_name=request.full_name.strip(),
            hashed_password=hashed,
            role="customer",
            is_active=True,
        )
        await self.repo.create_user(user)

        # Create initial session with new family_id
        access_token, refresh_token, csrf_token = await self._issue_session(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return user, access_token, refresh_token, csrf_token

    async def login(
        self,
        request: UserLoginRequest,
        client_ip: str,
        user_agent: str | None = None,
    ) -> tuple[User, str, str, str]:
        normalized_email = normalize_email(request.email)

        # Check rate limiter
        await login_rate_limiter.check_rate_limit(client_ip, normalized_email)

        user = await self.repo.get_user_by_email(normalized_email)
        if not user or not user.is_active:
            await login_rate_limiter.record_failure(client_ip, normalized_email)
            raise AppException(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                status_code=401,
            )

        if not verify_password(request.password, user.hashed_password):
            await login_rate_limiter.record_failure(client_ip, normalized_email)
            raise AppException(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                status_code=401,
            )

        # Login succeeded: clear failure counter
        await login_rate_limiter.record_success(client_ip, normalized_email)

        access_token, refresh_token, csrf_token = await self._issue_session(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return user, access_token, refresh_token, csrf_token

    async def refresh_token(
        self,
        plain_refresh_token: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, str]:
        token_hash = hash_token(plain_refresh_token)
        # Pessimistic row locking ensures concurrent requests with the same token serialize deterministically
        session = await self.repo.get_session_by_token_hash(token_hash, for_update=True)

        if not session:
            raise AppException(
                code="INVALID_REFRESH_TOKEN",
                message="Refresh token not recognized.",
                status_code=401,
            )

        # Check for token reuse / replay attack
        if session.is_revoked:
            # Revoke entire token family
            await self.repo.revoke_session_family(session.family_id)
            await self.session.commit()
            raise AppException(
                code="TOKEN_REVOKED",
                message="Revoked refresh token reuse detected. All sessions terminated.",
                status_code=401,
            )

        now = datetime.datetime.now(datetime.UTC)
        if session.expires_at <= now:
            await self.repo.revoke_session(session.id)
            await self.session.commit()
            raise AppException(
                code="REFRESH_TOKEN_EXPIRED",
                message="Refresh token has expired. Please log in again.",
                status_code=401,
            )

        # Check user status
        user = await self.repo.get_user_by_id(session.user_id)
        if not user or not user.is_active:
            await self.repo.revoke_session(session.id)
            await self.session.commit()
            raise AppException(
                code="USER_INACTIVE",
                message="User account is deactivated.",
                status_code=403,
            )

        # Rotate refresh token: revoke current session
        await self.repo.revoke_session(session.id)

        # Issue new token in the same family
        new_refresh_token = generate_refresh_token()
        new_token_hash = hash_token(new_refresh_token)
        new_session = UserSession(
            user_id=user.id,
            refresh_token_hash=new_token_hash,
            family_id=session.family_id,  # Preserve family
            is_revoked=False,
            user_agent=user_agent or session.user_agent,
            ip_address=client_ip or session.ip_address,
            expires_at=now
            + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.repo.create_session(new_session)

        new_access_token = create_access_token(
            user_id=user.id, role=user.role, session_id=new_session.id
        )
        csrf_token = generate_csrf_token()

        return new_access_token, new_refresh_token, csrf_token

    async def logout(self, plain_refresh_token: str | None) -> None:
        if not plain_refresh_token:
            return
        token_hash = hash_token(plain_refresh_token)
        session = await self.repo.get_session_by_token_hash(token_hash)
        if session and not session.is_revoked:
            await self.repo.revoke_session(session.id)

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.repo.revoke_all_user_sessions(user_id)

    async def get_user_profile(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get_user_by_id(user_id)
        if not user or not user.is_active:
            raise AppException(
                code="USER_NOT_FOUND",
                message="User not found or inactive.",
                status_code=404,
            )
        return user

    async def _issue_session(
        self,
        user: User,
        client_ip: str | None,
        user_agent: str | None,
        family_id: uuid.UUID | None = None,
    ) -> tuple[str, str, str]:
        plain_refresh = generate_refresh_token()
        token_hash = hash_token(plain_refresh)
        fam_id = family_id or uuid.uuid4()
        now = datetime.datetime.now(datetime.UTC)

        session = UserSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            family_id=fam_id,
            is_revoked=False,
            user_agent=user_agent,
            ip_address=client_ip,
            expires_at=now
            + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.repo.create_session(session)

        access_token = create_access_token(
            user_id=user.id, role=user.role, session_id=session.id
        )
        csrf_token = generate_csrf_token()

        return access_token, plain_refresh, csrf_token

    # ================= Address Services =================

    async def list_addresses(self, user_id: uuid.UUID) -> list[Address]:
        return await self.repo.get_addresses_by_user_id(user_id)

    async def create_address(
        self, user_id: uuid.UUID, request: AddressCreateRequest
    ) -> Address:
        # Lock user row to serialize address mutations and prevent concurrent default race conditions
        await self.repo.lock_user(user_id)

        existing_addresses = await self.repo.get_addresses_by_user_id(user_id)
        is_first = len(existing_addresses) == 0

        # If it's the first address or explicitly marked as default, clear existing defaults
        should_be_default = is_first or request.is_default
        if should_be_default:
            await self.repo.clear_default_addresses(user_id)

        address = Address(
            user_id=user_id,
            recipient_name=request.recipient_name.strip(),
            phone=request.phone.strip(),
            line1=request.line1.strip(),
            line2=request.line2.strip() if request.line2 else None,
            city=request.city.strip(),
            state=request.state.strip(),
            postal_code=request.postal_code.strip(),
            landmark=request.landmark.strip() if request.landmark else None,
            is_default=should_be_default,
        )
        return await self.repo.create_address(address)

    async def update_address(
        self, user_id: uuid.UUID, address_id: uuid.UUID, request: AddressUpdateRequest
    ) -> Address:
        # Lock user row when modifying default state to prevent concurrent default race conditions
        if request.is_default is not None:
            await self.repo.lock_user(user_id)

        address = await self.repo.get_address_by_id(address_id, user_id)
        if not address:
            raise AppException(
                code="ADDRESS_NOT_FOUND",
                message="Address not found.",
                status_code=404,
            )

        if request.is_default is True and not address.is_default:
            await self.repo.clear_default_addresses(user_id)
            address.is_default = True
        elif request.is_default is False and address.is_default:
            address.is_default = False

        if request.recipient_name is not None:
            address.recipient_name = request.recipient_name.strip()
        if request.phone is not None:
            address.phone = request.phone.strip()
        if request.line1 is not None:
            address.line1 = request.line1.strip()
        if request.line2 is not None:
            address.line2 = request.line2.strip() if request.line2.strip() else None
        if request.city is not None:
            address.city = request.city.strip()
        if request.state is not None:
            address.state = request.state.strip()
        if request.postal_code is not None:
            address.postal_code = request.postal_code.strip()
        if request.landmark is not None:
            address.landmark = (
                request.landmark.strip() if request.landmark.strip() else None
            )

        await self.session.flush()
        return address

    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        # Lock user row to serialize deletion and fallback default promotion
        await self.repo.lock_user(user_id)

        address = await self.repo.get_address_by_id(address_id, user_id)
        if not address:
            raise AppException(
                code="ADDRESS_NOT_FOUND",
                message="Address not found.",
                status_code=404,
            )

        was_default = address.is_default
        await self.repo.delete_address(address)

        if was_default:
            oldest = await self.repo.get_oldest_address(user_id)
            if oldest:
                oldest.is_default = True
                await self.session.flush()

    async def register_retailer(
        self,
        request: RetailerRegisterRequest,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, Any, str, str, str]:
        import re

        from sqlalchemy import select

        from app.modules.catalogue.models import Retailer

        normalized_email = normalize_email(request.email)
        existing_user = await self.repo.get_user_by_email(normalized_email)
        if existing_user:
            raise AppException(
                code="EMAIL_ALREADY_EXISTS",
                message="An account with this email already exists.",
                status_code=409,
            )

        base_slug = re.sub(r"[^a-z0-9]+", "-", request.store_name.lower()).strip("-")
        if not base_slug:
            base_slug = "store"
        slug = base_slug

        stmt = select(Retailer).where(Retailer.slug == slug)
        res = await self.session.execute(stmt)
        if res.scalar_one_or_none():
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        hashed = hash_password(request.password)
        user = User(
            email=normalized_email,
            phone=request.phone.strip(),
            full_name=request.full_name.strip(),
            hashed_password=hashed,
            role="retailer",
            is_active=True,
        )
        await self.repo.create_user(user)

        retailer = Retailer(
            id=uuid.uuid4(),
            user_id=user.id,
            name=request.store_name.strip(),
            slug=slug,
            description=request.description.strip()
            if request.description
            else f"{request.store_name.strip()} storefront on BASKET",
            state=request.state.strip().upper(),
            state_source="RETAILER_REGISTRATION",
            business_address=request.business_address.strip(),
            contact_phone=request.contact_phone.strip()
            if request.contact_phone
            else request.phone.strip(),
            contact_email=request.contact_email.strip()
            if request.contact_email
            else normalized_email,
            is_open=True,
            verification_status="PENDING",
            is_active=True,
        )
        self.session.add(retailer)
        await self.session.flush()

        access_token, refresh_token, csrf_token = await self._issue_session(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return user, retailer, access_token, refresh_token, csrf_token

    async def build_user_response(self, user: User) -> UserResponse:
        from sqlalchemy import select

        from app.modules.catalogue.models import Retailer

        retailer_id = None
        store_name = None
        verification_status = None

        if user.role == "retailer":
            stmt = select(Retailer).where(Retailer.user_id == user.id)
            res = await self.session.execute(stmt)
            retailer = res.scalar_one_or_none()
            if retailer:
                retailer_id = retailer.id
                store_name = retailer.name
                verification_status = retailer.verification_status

        return UserResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            retailer_id=retailer_id,
            store_name=store_name,
            verification_status=verification_status,
            created_at=user.created_at,
        )
