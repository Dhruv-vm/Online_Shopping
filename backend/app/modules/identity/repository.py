import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Address, User, UserSession


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ================= User Methods =================

    async def get_user_by_id(
        self, user_id: uuid.UUID, for_update: bool = False
    ) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def lock_user(self, user_id: uuid.UUID) -> User | None:
        """Pessimistically lock the user record to serialize concurrent address/cart operations."""
        return await self.get_user_by_id(user_id, for_update=True)

    async def get_user_by_email(self, normalized_email: str) -> User | None:
        stmt = select(User).where(User.email == normalized_email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    # ================= Session Methods =================

    async def create_session(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_session_by_id(self, session_id: uuid.UUID) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_session_by_token_hash(
        self, token_hash: str, for_update: bool = False
    ) -> UserSession | None:
        """Fetch session by token hash, optionally locking the row to prevent concurrent race conditions."""
        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_session(self, session_id: uuid.UUID) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)

    async def revoke_session_family(self, family_id: uuid.UUID) -> None:
        """Revoke all sessions in a family when token reuse is detected."""
        stmt = (
            update(UserSession)
            .where(UserSession.family_id == family_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> None:
        """Revoke all active sessions for a user (logout-all)."""
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)

    # ================= Address Methods =================

    async def get_addresses_by_user_id(self, user_id: uuid.UUID) -> list[Address]:
        stmt = (
            select(Address)
            .where(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_address_by_id(
        self, address_id: uuid.UUID, user_id: uuid.UUID
    ) -> Address | None:
        stmt = select(Address).where(
            Address.id == address_id, Address.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default_addresses(self, user_id: uuid.UUID) -> None:
        """Unset is_default flag for all addresses belonging to user."""
        stmt = (
            update(Address)
            .where(Address.user_id == user_id, Address.is_default.is_(True))
            .values(is_default=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_oldest_address(self, user_id: uuid.UUID) -> Address | None:
        """Retrieve oldest address to promote to default on deletion of default address."""
        stmt = (
            select(Address)
            .where(Address.user_id == user_id)
            .order_by(Address.created_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_address(self, address: Address) -> Address:
        self.session.add(address)
        await self.session.flush()
        return address

    async def delete_address(self, address: Address) -> None:
        await self.session.delete(address)
        await self.session.flush()
