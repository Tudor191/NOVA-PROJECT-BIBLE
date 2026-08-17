"""`HttpAdapter` -- `httpx.MockTransport`-backed, never a live server (same
convention `ollama_connector.py`'s own tests already use). The host
allow-list check itself runs before any request is made, so it needs no
transport at all to prove the sandbox-violation path."""

from __future__ import annotations

import httpx
import pytest
from nova_capability_engine.adapters.http_adapter import HttpAdapter
from nova_capability_engine.domain.sandbox import SandboxViolation


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"echo": request.url.path})


async def test_request_to_an_allowed_host_succeeds() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    adapter = HttpAdapter(client=client)

    result = await adapter.invoke(
        "request",
        {"method": "GET", "url": "https://api.example.com/v1/thing"},
        required_resources=["api.example.com"],
    )

    assert result["status_code"] == 200


async def test_request_to_a_disallowed_host_is_a_blocked_sandbox_violation_before_any_request() -> (
    None
):
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    adapter = HttpAdapter(client=client)

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke(
            "request",
            {"method": "GET", "url": "http://sandbox-probe.invalid/"},
            required_resources=["api.example.com"],
        )
    assert exc_info.value.adapter == "http"


async def test_unsupported_operation_raises_value_error() -> None:
    adapter = HttpAdapter()
    with pytest.raises(ValueError, match="download"):
        await adapter.invoke("download", {}, required_resources=[])
