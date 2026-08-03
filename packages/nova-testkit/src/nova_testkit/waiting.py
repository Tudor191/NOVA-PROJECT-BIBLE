"""Async polling helper for assertions on eventually-consistent state (e.g. "was
this event eventually published", "did this background worker finish"). This is the
alternative to sprinkling `asyncio.sleep(n)` through tests, which is both slow (always
waits the full `n`) and flaky (too short on a loaded CI runner).
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable

ConditionFn = Callable[[], "bool | Awaitable[bool]"]


async def wait_until(
    condition: ConditionFn, *, timeout_s: float = 2.0, interval_s: float = 0.01
) -> None:
    """Poll `condition` until it returns truthy, or raise `TimeoutError` after `timeout_s`."""
    deadline = time.monotonic() + timeout_s
    while True:
        result = condition()
        if inspect.isawaitable(result):
            result = await result
        if result:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Condition not met within {timeout_s}s")
        await asyncio.sleep(interval_s)
