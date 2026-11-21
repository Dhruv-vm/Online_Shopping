import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import AppException
from app.modules.identity.dependencies import (
    get_client_ip,
    get_current_active_user,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    AddressCreateRequest,
    AddressResponse,
    AddressUpdateRequest,
    AuthResponse,
    MessageResponse,
    RefreshTokenRequest,
    RetailerRegisterRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.identity.security import clear_auth_cookies, set_auth_cookies
from app.modules.identity.service import IdentityService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
user_router = APIRouter(prefix="/users", tags=["Users"])


@auth_router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register customer account",
)
async def register(
    request: Request,
    response: Response,
    body: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    service = IdentityService(db)
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    user, access_token, refresh_token, csrf_token = await service.register(
        request=body,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    await db.commit()

    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )


@auth_router.post(
    "/retailer/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new retailer account and store profile",
)
async def register_retailer(
    request: Request,
    response: Response,
    body: RetailerRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    service = IdentityService(db)
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    (
        user,
        retailer,
        access_token,
        refresh_token,
        csrf_token,
    ) = await service.register_retailer(
        request=body,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    await db.commit()

    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        retailer_id=retailer.id,
        store_name=retailer.name,
        verification_status=retailer.verification_status,
        preferred_language=getattr(user, "preferred_language", None) or "en",
        created_at=user.created_at,
    )

    return AuthResponse(
        user=user_resp,
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )


@auth_router.post(
    "/login",
    response_model=AuthResponse,
    summary="Customer login with rate limiting",
)
async def login(
    request: Request,
    response: Response,
    body: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    service = IdentityService(db)
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    user, access_token, refresh_token, csrf_token = await service.login(
        request=body,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    await db.commit()

    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
    )


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token with replay attack detection",
)
async def refresh_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RefreshTokenRequest | None = None,
    cookie_refresh: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> TokenResponse:
    token_str = (body.refresh_token if body else None) or cookie_refresh
    if not token_str:
        raise AppException(
            code="MISSING_REFRESH_TOKEN",
            message="Refresh token must be provided via cookie or request body.",
            status_code=401,
        )

    service = IdentityService(db)
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    new_access, new_refresh, csrf_token = await service.refresh_token(
        plain_refresh_token=token_str,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    await db.commit()

    set_auth_cookies(response, new_access, new_refresh, csrf_token)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        csrf_token=csrf_token,
    )


@auth_router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout and revoke active session",
    dependencies=[Depends(verify_csrf_token)],
)
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RefreshTokenRequest | None = None,
    cookie_refresh: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> MessageResponse:
    token_str = (body.refresh_token if body else None) or cookie_refresh
    if token_str:
        service = IdentityService(db)
        await service.logout(token_str)
        await db.commit()

    clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.")


@auth_router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke all active sessions for current user",
    dependencies=[Depends(verify_csrf_token)],
)
async def logout_all(
    response: Response,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = IdentityService(db)
    await service.logout_all(current_user.id)
    await db.commit()

    clear_auth_cookies(response)
    return MessageResponse(message="All active sessions terminated.")


@user_router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile with role context",
)
async def get_my_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    service = IdentityService(db)
    return await service.build_user_response(current_user)


address_router = APIRouter(prefix="/addresses", tags=["Addresses"])


@address_router.get(
    "",
    response_model=list[AddressResponse],
    summary="List saved addresses for current customer",
)
async def list_addresses(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AddressResponse]:
    service = IdentityService(db)
    addresses = await service.list_addresses(current_user.id)
    return [AddressResponse.model_validate(a) for a in addresses]


@address_router.post(
    "",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address for current customer",
    dependencies=[Depends(verify_csrf_token)],
)
async def create_address(
    body: AddressCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    service = IdentityService(db)
    address = await service.create_address(current_user.id, body)
    await db.commit()
    return AddressResponse.model_validate(address)


@address_router.patch(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Update an existing address",
    dependencies=[Depends(verify_csrf_token)],
)
async def update_address(
    address_id: uuid.UUID,
    body: AddressUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AddressResponse:
    service = IdentityService(db)
    address = await service.update_address(current_user.id, address_id, body)
    await db.commit()
    return AddressResponse.model_validate(address)


@address_router.delete(
    "/{address_id}",
    response_model=MessageResponse,
    summary="Delete an address",
    dependencies=[Depends(verify_csrf_token)],
)
async def delete_address(
    address_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = IdentityService(db)
    await service.delete_address(current_user.id, address_id)
    await db.commit()
    return MessageResponse(message="Address deleted successfully.")
