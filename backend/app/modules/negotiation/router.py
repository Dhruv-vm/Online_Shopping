import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_retailer,
    require_role,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.negotiation.schemas import (
    AcceptRequest,
    CounterOfferRequest,
    NegotiationSessionResponse,
    RuleItem,
    RuleUpsertRequest,
    StartRequest,
)
from app.modules.negotiation.service import NegotiationService

require_customer = require_role("customer")

router = APIRouter(
    prefix="/negotiate",
    tags=["AI Negotiator"],
    dependencies=[Depends(verify_csrf_token)],
)
retailer_router = APIRouter(
    prefix="/retailer/negotiation-rules",
    tags=["AI Negotiator (Retailer)"],
    dependencies=[Depends(require_retailer), Depends(verify_csrf_token)],
)


@router.post("/start", response_model=NegotiationSessionResponse, status_code=201)
async def start_negotiation(
    payload: StartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> NegotiationSessionResponse:
    return NegotiationService.to_response(
        await NegotiationService(db).start(user.id, payload)
    )


@router.post("/counter-offer", response_model=NegotiationSessionResponse)
async def counter_offer(
    payload: CounterOfferRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> NegotiationSessionResponse:
    return NegotiationService.to_response(
        await NegotiationService(db).counter(user.id, payload)
    )


@router.post("/accept", response_model=NegotiationSessionResponse)
async def accept_negotiation(
    payload: AcceptRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> NegotiationSessionResponse:
    """Lock the agreed price into a server-side checkout quote (15-minute validity).
    Continue checkout with POST /reservations {quote_id}."""
    s, quote = await NegotiationService(db).accept(user.id, payload)
    return NegotiationService.to_response(s, quote)


@router.get("/sessions/{session_id}", response_model=NegotiationSessionResponse)
async def get_negotiation(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> NegotiationSessionResponse:
    return NegotiationService.to_response(
        await NegotiationService(db).get(user.id, session_id)
    )


@retailer_router.get("", response_model=list[RuleItem])
async def list_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> list[RuleItem]:
    return [
        NegotiationService.rule_item(r)
        for r in await NegotiationService(db).list_rules(retailer)
    ]


@retailer_router.put("", response_model=RuleItem)
async def upsert_rule(
    payload: RuleUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> RuleItem:
    """Create or replace the storewide rule (listing_id null) or a listing rule."""
    return NegotiationService.rule_item(
        await NegotiationService(db).upsert_rule(retailer, payload)
    )


@retailer_router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> None:
    await NegotiationService(db).delete_rule(retailer, rule_id)
