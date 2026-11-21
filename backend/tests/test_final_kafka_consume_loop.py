"""Final cycle Part 13: Kafka consumers really poll in production.

Before this cycle the consumers joined their group but nothing ever called
poll_and_process_batch, so in Kafka mode no event was consumed.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.core.events.consumer import BaseKafkaConsumer
from app.core.search.consumer import OpenSearchConsumer
from app.modules.orders.consumer import OrderProjectionConsumer


@pytest.mark.asyncio
async def test_start_consuming_runs_poll_loop_until_stop():
    consumer = OrderProjectionConsumer(
        session_factory=AsyncMock(), producer=AsyncMock()
    )
    consumer._running = True
    calls = 0

    async def fake_poll(max_records: int = 50) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("broker hiccup")  # loop must survive and continue
        await asyncio.sleep(0)
        return 0

    consumer.poll_and_process_batch = fake_poll  # type: ignore[method-assign]
    consumer.start_consuming()
    for _ in range(300):
        if calls >= 3:
            break
        await asyncio.sleep(0.01)
    assert calls >= 3
    consumer._consumer = None
    await consumer.stop()
    assert consumer._consume_task.done()


def test_both_production_consumers_have_the_loop():
    assert issubclass(OpenSearchConsumer, BaseKafkaConsumer)
    assert issubclass(OrderProjectionConsumer, BaseKafkaConsumer)
    assert callable(BaseKafkaConsumer.start_consuming)
