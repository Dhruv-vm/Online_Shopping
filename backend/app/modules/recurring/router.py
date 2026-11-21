import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.identity.dependencies import require_role, verify_csrf_token
from app.modules.identity.models import User
from app.modules.recurring.schemas import (
    LoadToCartResult,
    PreOrderCheck,
    RecurringBasketCreate,
    RecurringBasketOut,
    RecurringBasketUpdate,
)
from app.modules.recurring.service import RecurringBasketService

require_customer = require_role("customer")

router = APIRouter(
    prefix="/recurring-baskets",
    tags=["Recurring Basket (Basket Monthly Essentials)"],
    dependencies=[Depends(verify_csrf_token)],
)

Customer = Annotated[User, Depends(require_customer)]
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=RecurringBasketOut, status_code=201)
async def create_recurring_basket(
    payload: RecurringBasketCreate, user: Customer, db: DB
):
    """Save the current cart as a monthly basket (schedule only; never charges)."""
    return await RecurringBasketService(db).create_from_cart(user.id, payload)


@router.get("", response_model=list[RecurringBasketOut])
async def list_recurring_baskets(user: Customer, db: DB):
    return await RecurringBasketService(db).list_baskets(user.id)


@router.get("/{basket_id}", response_model=RecurringBasketOut)
async def get_recurring_basket(basket_id: uuid.UUID, user: Customer, db: DB):
    return await RecurringBasketService(db).get(user.id, basket_id)


@router.patch("/{basket_id}", response_model=RecurringBasketOut)
async def update_recurring_basket(
    basket_id: uuid.UUID, payload: RecurringBasketUpdate, user: Customer, db: DB
):
    """Edit the schedule, delivery address, or item quantities (0 removes)."""
    return await RecurringBasketService(db).update(user.id, basket_id, payload)


@router.post("/{basket_id}/load-to-cart", response_model=LoadToCartResult)
async def load_recurring_basket(basket_id: uuid.UUID, user: Customer, db: DB):
    """Put the orderable items into the cart. The customer then checks out as usual."""
    return await RecurringBasketService(db).load_to_cart(user.id, basket_id)


@router.post("/{basket_id}/{action}", response_model=RecurringBasketOut)
async def change_recurring_basket_status(
    basket_id: uuid.UUID,
    action: Literal["pause", "resume", "skip", "cancel"],
    user: Customer,
    db: DB,
):
    """pause / resume / skip (the next date only) / cancel."""
    return await RecurringBasketService(db).set_status(user.id, basket_id, action)


@router.get("/{basket_id}/check", response_model=PreOrderCheck)
async def check_recurring_basket(basket_id: uuid.UUID, user: Customer, db: DB):
    """Pre-order check now: current price, stock, live offers, delivery, updated total."""
    return await RecurringBasketService(db).preview(user.id, basket_id)
