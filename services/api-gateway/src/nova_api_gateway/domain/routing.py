"""The forwarding route table -- decision **D-6**.

Doc 11 §2's documented endpoint list predates several engines and diverges
from what actually shipped: it names `/v1/conversations`, `/v1/memory/search`
and `/v1/autonomy/approvals/...`, while the code exposes
`/v1/communication/sessions`, `/v1/memories` and
`/v1/action/approvals/...`. D-6 resolved that by correcting the document
rather than translating in the gateway, so **paths are forwarded verbatim**.
A mapping layer between documented and real paths would be a permanent
source of drift.

The table is an allow-list, not a pattern. A prefix that is not listed is
not forwarded -- the gateway 404s rather than proxying anything a caller
names. 4B extends this with planning/reasoning/capability/action; the
mechanism does not change, only the entries.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Endpoint classes for rate limiting, doc 11 §5.
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class UpstreamRoute:
    """One fronted engine."""

    prefix: str
    upstream_name: str
    base_url: str


class RouteTable:
    def __init__(self, routes: list[UpstreamRoute]) -> None:
        for route in routes:
            if not route.prefix.startswith("/v1/"):
                raise ValueError(
                    f"route prefix {route.prefix!r} must start with '/v1/'. "
                    "Only the versioned external surface is forwardable; "
                    "'/internal/*' is never routable through the gateway "
                    "(doc 11 §3)."
                )
        # Longest prefix first, so a more specific route always wins over a
        # more general one regardless of declaration order.
        self._routes = sorted(routes, key=lambda r: len(r.prefix), reverse=True)

    def resolve(self, path: str) -> UpstreamRoute | None:
        for route in self._routes:
            if path == route.prefix or path.startswith(route.prefix.rstrip("/") + "/"):
                return route
        return None

    @property
    def routes(self) -> tuple[UpstreamRoute, ...]:
        return tuple(self._routes)


def endpoint_class(method: str) -> str:
    return "read" if method.upper() in READ_METHODS else "write"


def build_route_table(
    *,
    communication_engine_url: str,
    planning_engine_url: str,
    reasoning_engine_url: str,
    capability_engine_url: str,
    action_engine_url: str,
) -> RouteTable:
    """Every engine the gateway fronts, and nothing else.

    4A fronted `communication-engine` alone. 4B adds the four the
    observability panels read from -- exactly as this module predicted, by
    appending entries rather than changing the mechanism. Each engine's `/v1`
    surface already existed; no engine API was changed to be fronted.

    Deliberately absent:

    * `executive-cognition-engine` -- it has a `/v1/executive/decisions`
      surface, but no 4B panel reads it. Fronting an engine no panel uses
      would widen the external attack surface for nothing.
    * `nova-core` -- exposes only `/internal/*`, which is never routable
      (doc 11 §3). The Health panel is fed by bus telemetry instead.

    Every prefix here is a **panel's** data source. Adding one because an
    engine happens to exist is how an allow-list stops being one.
    """
    return RouteTable(
        [
            UpstreamRoute(
                prefix="/v1/communication",
                upstream_name="communication-engine",
                base_url=communication_engine_url.rstrip("/"),
            ),
            # Planning panel.
            UpstreamRoute(
                prefix="/v1/plans",
                upstream_name="planning-engine",
                base_url=planning_engine_url.rstrip("/"),
            ),
            # Reasoning Trace panel.
            UpstreamRoute(
                prefix="/v1/reasoning",
                upstream_name="reasoning-engine",
                base_url=reasoning_engine_url.rstrip("/"),
            ),
            # Capabilities panel.
            UpstreamRoute(
                prefix="/v1/capabilities",
                upstream_name="capability-engine",
                base_url=capability_engine_url.rstrip("/"),
            ),
            # Approvals panel.
            UpstreamRoute(
                prefix="/v1/action",
                upstream_name="action-engine",
                base_url=action_engine_url.rstrip("/"),
            ),
        ]
    )
