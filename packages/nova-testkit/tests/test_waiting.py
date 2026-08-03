import asyncio

import pytest
from nova_testkit import wait_until


async def test_wait_until_returns_once_sync_condition_is_true() -> None:
    state = {"ready": False}

    async def flip_soon() -> None:
        await asyncio.sleep(0.02)
        state["ready"] = True

    asyncio.create_task(flip_soon())
    await wait_until(lambda: state["ready"], timeout_s=1.0)
    assert state["ready"] is True


async def test_wait_until_supports_async_condition() -> None:
    state = {"count": 0}

    async def condition() -> bool:
        state["count"] += 1
        return state["count"] >= 3

    await wait_until(condition, timeout_s=1.0, interval_s=0.001)
    assert state["count"] >= 3


async def test_wait_until_raises_timeout_error_when_never_true() -> None:
    with pytest.raises(TimeoutError):
        await wait_until(lambda: False, timeout_s=0.05, interval_s=0.01)
