"""`http` built-in adapter (TDD 3C §3): outbound-host allow-list (declared
domains only), per-request timeout, no arbitrary redirect-following beyond
the allow-list. `httpx` is lazily imported (same convention
`ai-model-orchestration-engine`'s own connectors already use) and its
client is injectable for tests (`httpx.MockTransport`), never a live
server in unit tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from nova_capability_engine.domain.sandbox import check_host_allowed

if TYPE_CHECKING:
    import httpx

__all__ = ["HttpAdapter"]

_DEFAULT_TIMEOUT_S = 10.0


class HttpAdapter:
    name = "http"

    def __init__(
        self, *, timeout_s: float = _DEFAULT_TIMEOUT_S, client: httpx.AsyncClient | None = None
    ) -> None:
        self._timeout_s = timeout_s
        self._client = client

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self._timeout_s, follow_redirects=False)
        return self._client

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict:
        if operation != "request":
            raise ValueError(f"http adapter does not support operation {operation!r}")
        url = parameters["url"]
        host = urlsplit(url).hostname or ""
        check_host_allowed(host, allowed_hosts=required_resources)
        method = parameters.get("method", "GET")
        client = self._ensure_client()
        response = await client.request(method, url, json=parameters.get("body"))
        return {
            "status_code": response.status_code,
            "body": response.text,
            "headers": dict(response.headers),
        }
