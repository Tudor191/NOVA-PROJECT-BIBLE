"""nova-testkit: shared pytest fixtures and async test helpers for every engine.

The `event_bus` and `fake_model_gateway` fixtures are registered globally via
the `pytest11` entry point (see `plugin.py`) and do not need to be imported
here. `FakeModelGateway` itself is exported for tests that want to construct
one with non-default configuration (`should_fail=True`, a custom
`response_text`, etc.) rather than using the fixture's defaults.
"""

from nova_testkit.model_gateway import FakeModelGateway
from nova_testkit.waiting import wait_until

__all__ = ["FakeModelGateway", "wait_until"]
