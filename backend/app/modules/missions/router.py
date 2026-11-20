import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.identity.dependencies import (
    get_current_active_user,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.missions.schemas import (
    MissionAddToCartResponse,
    MissionAlternativeItemResponse,
    MissionCreateRequest,
    MissionDetailResponse,
    MissionItemAddRequest,
    MissionItemReplaceRequest,
    MissionItemUpdateRequest,
    MissionSummaryResponse,
    MissionUpdateRequest,
)
from app.modules.missions.service import MissionService

router = APIRouter(prefix="/missions", tags=["Basket Mission"])


@router.post(
    "",
    response_model=MissionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf_token)],
    summary="Create a new Basket Mission and generate recommended shopping plan",
)
async def create_mission(
    payload: MissionCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.create_mission(customer_id=current_user.id, payload=payload)


@router.post(
    "/preview",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Generate an interactive mission plan preview without persisting",
)
async def preview_mission_plan(
    payload: MissionCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = MissionService(db)
    return await service.preview_plan(payload=payload)


@router.get(
    "",
    response_model=list[MissionSummaryResponse],
    summary="List all missions saved by the authenticated customer",
)
async def list_customer_missions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MissionSummaryResponse]:
    service = MissionService(db)
    return await service.list_missions(customer_id=current_user.id)


@router.get(
    "/{mission_id}",
    response_model=MissionDetailResponse,
    summary="Retrieve full mission details, grouped items, live prices and stock",
)
async def get_mission_detail(
    mission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.get_mission(customer_id=current_user.id, mission_id=mission_id)


@router.patch(
    "/{mission_id}",
    response_model=MissionDetailResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update mission title, budget, description or status",
)
async def update_mission(
    mission_id: uuid.UUID,
    payload: MissionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.update_mission(
        customer_id=current_user.id, mission_id=mission_id, payload=payload
    )


@router.delete(
    "/{mission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf_token)],
    summary="Delete a customer mission",
)
async def delete_mission(
    mission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = MissionService(db)
    await service.delete_mission(customer_id=current_user.id, mission_id=mission_id)


@router.post(
    "/{mission_id}/items",
    response_model=MissionDetailResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Add an additional marketplace product listing to a mission",
)
async def add_mission_item(
    mission_id: uuid.UUID,
    payload: MissionItemAddRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.add_item(
        customer_id=current_user.id, mission_id=mission_id, payload=payload
    )


@router.patch(
    "/{mission_id}/items/{item_id}",
    response_model=MissionDetailResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Update item quantity or toggle selection",
)
async def update_mission_item(
    mission_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: MissionItemUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.update_item(
        customer_id=current_user.id,
        mission_id=mission_id,
        item_id=item_id,
        payload=payload,
    )


@router.delete(
    "/{mission_id}/items/{item_id}",
    response_model=MissionDetailResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Remove an item from a mission",
)
async def delete_mission_item(
    mission_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.delete_item(
        customer_id=current_user.id, mission_id=mission_id, item_id=item_id
    )


@router.get(
    "/{mission_id}/items/{item_id}/alternatives",
    response_model=list[MissionAlternativeItemResponse],
    summary="Find alternative products from the same category with available stock and price delta",
)
async def get_mission_item_alternatives(
    mission_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MissionAlternativeItemResponse]:
    service = MissionService(db)
    return await service.get_item_alternatives(
        customer_id=current_user.id, mission_id=mission_id, item_id=item_id
    )


@router.post(
    "/{mission_id}/items/{item_id}/replace",
    response_model=MissionDetailResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Replace a mission item with an alternative product listing",
)
async def replace_mission_item(
    mission_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: MissionItemReplaceRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionDetailResponse:
    service = MissionService(db)
    return await service.replace_item(
        customer_id=current_user.id,
        mission_id=mission_id,
        item_id=item_id,
        payload=payload,
    )


@router.post(
    "/{mission_id}/add-to-cart",
    response_model=MissionAddToCartResponse,
    dependencies=[Depends(verify_csrf_token)],
    summary="Add all selected mission products to customer's active shopping basket",
)
async def add_mission_to_cart(
    mission_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MissionAddToCartResponse:
    service = MissionService(db)
    return await service.add_to_cart(customer_id=current_user.id, mission_id=mission_id)
