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
    agent_os_kernel_url: str,
    autonomy_engine_url: str,
    digital_twin_engine_url: str,
) -> RouteTable:
    """Every engine the gateway fronts, and nothing else.

    4A fronted `communication-engine` alone. 4B adds the four the
    observability panels read from, 4C the Agents panel's Kernel, 4D the
    Autonomy panel and 4E the Digital Twin panel -- exactly as this module
    predicted, by appending entries rather than changing the mechanism. Each
    engine's `/v1` surface already existed; no engine API was changed to be
    fronted.

    Deliberately absent:

    * `executive-cognition-engine` -- it has a `/v1/executive/decisions`
      surface, but no 4B panel reads it. Fronting an engine no panel uses
      would widen the external attack surface for nothing.
    * `nova-core` -- exposes only `/internal/*`, which is never routable
      (doc 11 §3). The Health panel is fed by bus telemetry instead.
    * `agent-os/registry` and `agent-os/supervisors` -- neither has a `/v1`
      surface, and neither needs one: the Agents panel reads packages through
      the Kernel, which asks Registry over the bus (ADR-004). Fronting them
      would expose two components no panel talks to.

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
            # Agents panel (Phase 4C, decision D-4). The first upstream here
            # that is not a `services/*` engine -- `agent-os/kernel` is
            # control-plane infrastructure -- which changes nothing about the
            # mechanism: one prefix, one upstream, forwarded 1:1.
            #
            # `/v1/agents/{id}` and `/v1/agents/{id}/activity` need no entries
            # of their own: `resolve()` matches on prefix, so the whole
            # subtree forwards to the Kernel. That is also why nothing here
            # can reach `/internal/*` -- `RouteTable` refuses any prefix
            # outside `/v1/` at construction.
            UpstreamRoute(
                prefix="/v1/agents",
                upstream_name="agent-os-kernel",
                base_url=agent_os_kernel_url.rstrip("/"),
            ),
            # Autonomy panel (Phase 4D). `/v1/autonomy` and its whole subtree
            # -- levels, policies, permissions, suggestions -- forwarded 1:1
            # (D-6), by appending one entry rather than changing the mechanism.
            #
            # This is **not** a duplicate of `/v1/action` above. TDD 4D §8.1
            # draws the boundary: `action-engine`'s approval endpoint decides
            # one already-created Action inside its execution pipeline;
            # `/v1/autonomy/*` governs whether NOVA may act at all. Both exist,
            # neither is reachable from the other's domain, and neither is
            # deprecated.
            UpstreamRoute(
                prefix="/v1/autonomy",
                upstream_name="autonomy-engine",
                base_url=autonomy_engine_url.rstrip("/"),
            ),
            # Digital Twin panel (Phase 4E). `/v1/digital-twin` and its whole
            # subtree, forwarded 1:1 (D-6) -- one more entry, same mechanism.
            #
            # **This prefix fronts more than 4E's five routes, and that is the
            # correct outcome rather than an oversight.** `resolve()` matches on
            # prefix, so Phase 2D-D's `/profile`, `/preferences`,
            # `/proactive-policy` and `/reset` become reachable too. They were
            # always part of the same engine's `/v1` surface and were simply
            # unfronted because no panel read them; the Digital Twin panel now
            # does. Carving 4E's five out individually would mean either five
            # entries that drift from the engine, or a path-rewriting layer --
            # which is precisely what D-6 rejected as a permanent source of
            # drift.
            #
            # Nothing under `/internal/*` becomes reachable: `RouteTable` refuses
            # any prefix outside `/v1/` at construction.
            UpstreamRoute(
                prefix="/v1/digital-twin",
                upstream_name="digital-twin-engine",
                base_url=digital_twin_engine_url.rstrip("/"),
            ),
        ]
    )
