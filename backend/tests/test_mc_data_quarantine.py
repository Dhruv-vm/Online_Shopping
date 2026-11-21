"""The fixture quarantine must hide test data and restore it exactly."""

import pytest
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import Retailer
from app.modules.identity.models import User
from app.seeds.quarantine_test_data import restore, run
from tests.phase3_helpers import make_retailer


@pytest.mark.asyncio
async def test_quarantine_round_trip_restores_every_record():
    listing, _ = await make_retailer(selling_price_paise=10000)
    async with get_session_factory()() as s:
        ret = await s.get(Retailer, __import__("uuid").UUID(listing["retailer_id"]))
        owner = await s.get(User, ret.user_id)
        assert owner.email.endswith("@example.com")
        before = (ret.is_active, ret.is_open, owner.is_active)

    dry = await run(apply=False)
    assert dry["batch_id"] is None and dry["retailer"] >= 1

    result = await run(apply=True)
    batch = result["batch_id"]
    async with get_session_factory()() as s:
        ret = await s.get(Retailer, ret.id)
        owner = await s.get(User, owner.id)
        assert (ret.is_active, ret.is_open, owner.is_active) == (False, False, False)
        # demo / non-test accounts are never touched
        demo = (
            (await s.execute(select(User).where(User.email.like("%@basket.demo"))))
            .scalars()
            .all()
        )
        assert all(u.is_active for u in demo)

    restored = await restore(batch)
    assert restored >= 2
    async with get_session_factory()() as s:
        ret = await s.get(Retailer, ret.id)
        owner = await s.get(User, owner.id)
        assert (ret.is_active, ret.is_open, owner.is_active) == before
