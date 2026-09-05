"""HTTP forwarding to a fronted engine.

The gateway is the first component in this project to make outbound HTTP
calls to another engine: every existing engine-to-engine path goes over the
Event Bus (ADR-006). That is not an inconsistency. The gateway's job is to
front already-built `/v1` REST surfaces for the outside world, and doc 11 §1
describes exactly that -- forwarding to the owning engine. It publishes no
events of its own and subscribes to none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

#: Hop-by-hop headers, plus the ones the gateway must own rather than relay.
#: `host` would point the upstream at the gateway's own name; `cookie` carries
#: the session credential, which must never leak past the trust boundary.
_REQUEST_HEADER_DENYLIST = frozenset(
    {
        "host",
        "cookie",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "content-length",
        "authorization",
    }
)

_RESPONSE_HEADER_DENYLIST = frozenset(
    {
        "connection",
        "keep-alive",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
        "set-cookie",
    }
)


class UpstreamUnavailableError(RuntimeError):
    """The upstream could not be reached, or did not answer in time.

    Raised rather than swallowed so the caller returns a structured error.
    A gateway that turned an unreachable engine into an empty success would
    make the UI display a belief NOVA does not hold.
    """


@dataclass(frozen=True)
class UpstreamResponse:
    status_code: int
    json_body: object | None
    text_body: str
    headers: dict[str, str]


def filter_request_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _REQUEST_HEADER_DENYLIST}


def filter_response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in headers.items() if k.lower() not in _RESPONSE_HEADER_DENYLIST
    }


class UpstreamClient:
    """Thin, typed wrapper over one `httpx.AsyncClient`."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def forward(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: Sequence[tuple[str, str]] | None = None,
        content: bytes | None = None,
    ) -> UpstreamResponse:
        try:
            response = await self._client.request(
                method,
                url,
                headers=filter_request_headers(headers),
                params=list(params) if params is not None else None,
                content=content,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamUnavailableError(f"upstream timed out: {url}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError(f"upstream unreachable: {url}") from exc

        try:
            json_body: object | None = response.json()
        except ValueError:
            json_body = None

        return UpstreamResponse(
            status_code=response.status_code,
            json_body=json_body,
            text_body=response.text,
            headers=filter_response_headers(dict(response.headers)),
        )
