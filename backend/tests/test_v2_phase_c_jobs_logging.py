"""Version 2.0 Phase C3 (concurrency-safe periodic jobs) and C4 (logging
hygiene). Overlap is simulated with real concurrent database sessions."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.background import job_lock_key, run_in_txn, run_job
from app.core.config import Settings
from app.core.database import get_engine, get_session_factory
from app.core.logging import SanitizeFormatter, redact_secrets
from app.modules.auctions.models import BasketAuction
from app.modules.auctions.service import close_ended_auctions
from app.modules.community.models import GroupBuyCampaign, GroupBuyMember
from app.modules.community.service import settle_expired_campaigns
from app.modules.orders.models import CustomerNotification
from app.modules.pricing.models import PriceAward
from tests.phase3_helpers import make_retailer, make_user


def _job_lines(caplog, name):
    out = []
    for r in caplog.records:
        msg = r.getMessage()
        if msg.startswith("job_run "):
            rec = json.loads(msg[len("job_run ") :])
            if rec["job"] == name:
                out.append(rec)
    return out


# ------------------------------------------------------------- advisory lock
@pytest.mark.asyncio
async def test_overlapping_runs_of_one_job_never_run_together(caplog):
    caplog.set_level(logging.INFO, logger="app.core.background")
    sf = get_session_factory()
    name = f"v2c-test-{uuid.uuid4().hex[:8]}"
    running = 0
    peak = 0
    entered = asyncio.Event()

    async def body():
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        entered.set()
        await asyncio.sleep(0.3)
        running -= 1
        return 7

    async def second():
        await entered.wait()
        return await run_job(sf, name, body)

    first, other = await asyncio.gather(run_job(sf, name, body), second())
    assert peak == 1
    assert {first["status"], other["status"]} == {"ok", "skipped"}
    ok = first if first["status"] == "ok" else other
    assert ok["rows"] == 7
    # The lock is released at the end of the run: the next cycle runs.
    again = await run_job(sf, name, body)
    assert again["status"] == "ok"
    # Exactly one structured line per run.
    lines = _job_lines(caplog, name)
    assert [x["status"] for x in lines].count("skipped") == 1
    assert [x["status"] for x in lines].count("ok") == 2
    assert all(x["run_id"] and x["duration_ms"] is not None for x in lines)


@pytest.mark.asyncio
async def test_different_jobs_do_not_block_each_other():
    sf = get_session_factory()

    async def body():
        await asyncio.sleep(0.2)
        return 1

    a, b = await asyncio.gather(
        run_job(sf, f"v2c-a-{uuid.uuid4().hex[:6]}", body),
        run_job(sf, f"v2c-b-{uuid.uuid4().hex[:6]}", body),
    )
    assert a["status"] == b["status"] == "ok"
    assert job_lock_key("x") == job_lock_key("x") != job_lock_key("y")


@pytest.mark.asyncio
async def test_failed_run_is_logged_redacted_and_retryable(caplog):
    caplog.set_level(logging.INFO, logger="app.core.background")
    sf = get_session_factory()
    name = f"v2c-fail-{uuid.uuid4().hex[:8]}"

    async def boom():
        raise RuntimeError(
            "cannot reach postgresql://basket:SuperSecret1@db:5432/x token=abc123"
        )

    with pytest.raises(RuntimeError):
        await run_job(sf, name, boom)
    (line,) = _job_lines(caplog, name)
    assert line["status"] == "failed" and "RuntimeError" in line["error"]
    assert "SuperSecret1" not in line["error"] and "abc123" not in line["error"]

    async def fine():
        return 0

    assert (await run_job(sf, name, fine))["status"] == "ok"  # lock was released


# -------------------------------------------------------- business idempotency
@pytest.mark.asyncio
async def test_concurrent_auction_closers_notify_once(async_client: AsyncClient):
    pin = "400001"
    base, base_h = await make_retailer(
        service_pincodes=[pin], selling_price_paise=50000, original_price_paise=60000
    )
    cust_id, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 1},
    )
    a = (
        await async_client.post(
            "/api/v1/auctions/start", headers=cust, json={"pincode": pin}
        )
    ).json()
    bid = await async_client.post(
        f"/api/v1/retailer/auctions/{a['id']}/bid",
        headers=base_h,
        json={"bid_price_paise": 45000, "delivery_eta_minutes": 20},
    )
    assert bid.status_code == 201, bid.text
    sf = get_session_factory()
    async with sf() as s:
        row = await s.get(BasketAuction, uuid.UUID(a["id"]))
        row.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()

    # Two "instances" run the closer at the same moment (no advisory lock here:
    # this exercises the row-level SKIP LOCKED claim + transition check).
    await asyncio.gather(
        run_in_txn(sf, close_ended_auctions), run_in_txn(sf, close_ended_auctions)
    )
    await run_in_txn(sf, close_ended_auctions)  # and a later overlapping cycle
    async with sf() as s:
        assert (await s.get(BasketAuction, uuid.UUID(a["id"]))).status == "COMPLETED"
        n = (
            await s.execute(
                select(func.count())
                .select_from(CustomerNotification)
                .where(
                    CustomerNotification.customer_id == cust_id,
                    CustomerNotification.event_type == "AUCTION_COMPLETED",
                )
            )
        ).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_concurrent_group_buy_settlement_awards_and_notifies_once(
    async_client: AsyncClient,
):
    listing, rh = await make_retailer(
        selling_price_paise=40000, original_price_paise=50000
    )
    camp = (
        await async_client.post(
            "/api/v1/retailer/community-buying/campaigns",
            headers=rh,
            json={
                "min_participants": 2,
                "max_participants": 3,
                "discount_percent": 25,
                "duration_hours": 24,
                "listing_id": listing["id"],
            },
        )
    ).json()
    members = []
    for _ in range(2):
        uid, h = await make_user()
        j = await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/join",
            headers=h,
            json={"quantity": 1},
        )
        assert j.status_code == 200, j.text
        members.append(uid)
    sf = get_session_factory()
    async with sf() as s:
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        c.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()

    # Overlapping workers: two closers at once, both through run_job (as the
    # supervisor does) and directly (row-level guard only).
    await asyncio.gather(
        run_job(
            sf,
            "phase3.settle_expired_campaigns",
            lambda: run_in_txn(sf, settle_expired_campaigns),
        ),
        run_job(
            sf,
            "phase3.settle_expired_campaigns",
            lambda: run_in_txn(sf, settle_expired_campaigns),
        ),
        run_in_txn(sf, settle_expired_campaigns),
    )
    async with sf() as s:
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        assert c.status == "SUCCESSFUL"
        awards = (
            (
                await s.execute(
                    select(PriceAward.customer_id).where(
                        PriceAward.source_id == c.id, PriceAward.source == "GROUP_BUY"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(awards, key=str) == sorted(members, key=str)  # one each
        for uid in members:
            n = (
                await s.execute(
                    select(func.count())
                    .select_from(CustomerNotification)
                    .where(
                        CustomerNotification.customer_id == uid,
                        CustomerNotification.title == "Group discount unlocked!",
                    )
                )
            ).scalar_one()
            assert n == 1
        statuses = (
            (
                await s.execute(
                    select(GroupBuyMember.status).where(
                        GroupBuyMember.campaign_id == c.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert statuses == ["AWARDED", "AWARDED"]


# ------------------------------------------------------------------ logging
def test_sql_echo_is_separate_from_debug_and_off_by_default(monkeypatch):
    monkeypatch.delenv("SQL_ECHO", raising=False)
    cfg = Settings(DEBUG=True, _env_file=None)
    assert cfg.SQL_ECHO is False
    assert Settings(SQL_ECHO=True, _env_file=None).SQL_ECHO is True
    engine = get_engine()
    assert engine is not None and engine.echo is False


def test_log_formatter_masks_credentials():
    fmt = SanitizeFormatter("%(message)s")
    rec = logging.LogRecord(
        "x",
        logging.ERROR,
        __file__,
        1,
        "connect failed postgresql+asyncpg://u:hunter2@h/db key_secret=abc",
        None,
        None,
    )
    out = fmt.format(rec)
    assert "hunter2" not in out and "abc" not in out.split("key_secret=")[1]
    assert "connect failed" in out  # the real error stays visible
    assert redact_secrets("plain error 42") == "plain error 42"
