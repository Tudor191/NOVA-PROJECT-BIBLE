# nova-testkit

Shared pytest fixtures and async test helpers for every NOVA engine
(docs/architecture/16-testing-strategy.md §3).

- **`event_bus` fixture** (auto-registered via the `pytest11` entry point -- no
  `conftest.py` needed): a connected, isolated `InMemoryEventBus` per test.
- **`wait_until(condition, timeout_s=2.0)`**: poll an eventually-true condition
  instead of `asyncio.sleep(n)`.

## Usage

Add `nova-testkit` as a dev dependency of your engine, then just use the fixture:

```python
async def test_something(event_bus):
    ...
```
