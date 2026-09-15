"""Phase 4E's ten negative and security controls -- TDD 4E Sec14.5.

| # | Property |
|---|---|
| 1 | No new Event Bus subject is registered by this engine |
| 2 | `ws-gateway`'s `PUBLIC_TOPICS` is byte-identical at its 18 exact strings |
| 3 | No cross-engine import (import-linter, plus an AST check here) |
| 4 | No write to `memory-engine` or `perception-engine` |
| 5 | A domain with no evidence rows cannot report `populated`; the two 4F domains cannot report anything but `empty`/`unavailable` |
| 6 | A restricted memory never reaches a rendered domain |
| 7 | Only the five Sec7 routes are published, asserted against the OpenAPI document |
| 8 | No `autonomy.*` subject and no autonomy behaviour |
| 9 | CF-10 is not resolved by 4E -- five separate sub-properties |
| 10 | Every non-`populated` state carries a machine-readable reason |

Contract tests rather than unit tests because each asserts a property of the
**repository**, not of a function: the strongest form of *"4E introduced no new
subject"* is that no such subject exists anywhere.

**Source checks parse the AST, never raw text** -- 4D's own lesson, and it applies
with more force here: this engine's prose names `TrustMetric`, `memory-engine` and
`autonomy` repeatedly while explaining why it does not touch them, and a control
that fires on its own rationale is a control that gets loosened. `_code_of`
strips docstrings and comments so the checks see only what executes.
"""  # noqa: E501 -- the table row does not read better wrapped

from __future__ import annotations

import ast
from pathlib import Path

import nova_digital_twin_engine
import pytest
from fastapi.testclient import TestClient
from nova_contracts.registry import known_subjects
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_digital_twin_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository

_SOURCE_ROOT = Path(nova_digital_twin_engine.__file__).parent
_REPO_ROOT = Path(nova_digital_twin_engine.__file__).parents[4]


def _source_files() -> list[Path]:
    return sorted(_SOURCE_ROOT.rglob("*.py"))


def _is_bare_string(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Remove **every** bare string-literal statement, not only the leading one --
    this codebase documents constants and model fields with PEP 258 attribute
    docstrings, so stripping `body[0]` alone would leave most of its prose in the
    "code"."""
    for node in ast.walk(tree):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        node.body = [s for s in node.body if not _is_bare_string(s)] or [ast.Pass()]
    return tree


def _code_of(path: Path) -> str:
    return ast.unparse(_strip_docstrings(ast.parse(path.read_text())))


@pytest.fixture(autouse=True)
def _in_memory_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


# --- Control 1: no new Event Bus subject ------------------------------------


def test_control_1_this_engine_publishes_exactly_what_2dd_shipped() -> None:
    """`PUBLISHABLE_SUBJECTS` is byte-identical to Phase 2D-D's. 4E publishes
    nothing (Sec8.2), so a subject added here could not reach the wire."""
    assert frozenset(
        {
            "communication.intent.deliver.request",
            "communication.session.lookup_by_user.request",
        }
    ) == PUBLISHABLE_SUBJECTS


def test_control_1_the_three_new_subscriptions_all_predate_4e() -> None:
    """4E is a **consumer of existing contracts**. Each subject already has a
    registered payload and a real publisher; none was registered by this
    milestone."""
    registered = set(known_subjects())
    for subject in (
        "memory.long_term.created",
        "memory.decision.recorded",
        "perception.attention.observed",
    ):
        assert subject in SUBSCRIBABLE_SUBJECTS
        assert subject in registered, f"{subject} has no registered payload"


def test_control_1_no_digital_twin_subject_beyond_the_2dd_rpc_pair() -> None:
    """The repository-wide half. `digital_twin.preferences.get.request`/`.reply`
    are 2D-D's served RPC and its reply payload; 4E claims no `digital_twin.*`
    subject of its own."""
    claimed = [s for s in known_subjects() if s.startswith("digital_twin.")]
    assert claimed == [
        "digital_twin.preferences.get.reply",
        "digital_twin.preferences.get.request",
    ]


# --- Control 2: PUBLIC_TOPICS is byte-identical -----------------------------


_EXPECTED_PUBLIC_TOPICS = frozenset(
    {
        "action.approval.decided",
        "action.approval.requested",
        "agent_os.task.completed",
        "ai_model.model.health_changed",
        "communication.intent.delivered",
        "communication.session.completed",
        "communication.session.created",
        "communication.session.state_changed",
        "communication.turn.received",
        "nova.heartbeat",
        "nova.module.status_changed",
        "perception.identity.observed",
        "perception.presence.observed",
        "perception.sensor.health_changed",
        "planning.task_graph.created",
        "reasoning.human_override.applied",
        "reasoning.process.completed",
        "reasoning.process.failed",
    }
)
"""`ws-gateway`'s allow-list as Phase 4D left it, transcribed from the module
rather than from any document. The three `perception.*` entries are `presence`,
`identity` and `sensor.health_changed`; note that `perception.attention.observed`
-- which 4E now *subscribes* to, engine-side -- is deliberately **not** among
them, so consuming it gives the browser no new reach."""


def test_control_2_public_topics_is_unchanged_at_eighteen_exact_strings() -> None:
    """**Sec8.3 and Sec10 item 2.** The Digital Twin is a slowly-evolving derived
    model, not a live event stream, so the panel reads REST and refreshes
    explicitly -- the same reasoning D-4D-1 applied to autonomy suggestions.

    Asserted as a literal set, so *adding* a topic fails as loudly as removing
    one. `PUBLIC_TOPICS` is how three dead topics reached the browser before 4A
    caught them, and no `digital_twin.*` entry joins it here.
    """
    from nova_ws_gateway.domain.protocol import PUBLIC_TOPICS

    assert PUBLIC_TOPICS == _EXPECTED_PUBLIC_TOPICS
    assert len(PUBLIC_TOPICS) == 18
    assert not [t for t in PUBLIC_TOPICS if t.startswith("digital_twin.")]


# --- Control 3: no cross-engine import --------------------------------------


_OTHER_ENGINE_MODULES = (
    "nova_memory_engine",
    "nova_perception_engine",
    "nova_personality_engine",
    "nova_autonomy_engine",
    "nova_action_engine",
    "nova_api_gateway",
    "nova_ws_gateway",
)


def test_control_3_no_module_imports_another_engines_internals() -> None:
    """ADR-004, enforced here as well as by `lint-imports`.

    This is the control that makes Sec0.1.5's correction mechanical rather than
    documentary: the withdrawn HTTP read would have needed one of these imports
    or an httpx client, and both are checked.
    """
    offenders: list[str] = []
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] in _OTHER_ENGINE_MODULES:
                    offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"cross-engine imports: {offenders}"


def test_control_3_no_http_client_reaches_another_engine() -> None:
    """ADR-004's *"never a raw HTTP call from one engine's code straight into
    another engine's module"* (Sec0.1.5). This engine has no HTTP client at all:
    it talks to `communication-engine` over the bus and to nothing else."""
    for path in _source_files():
        code = _code_of(path)
        assert "httpx" not in code, f"{path.name} reaches for an HTTP client"
        assert "aiohttp" not in code, f"{path.name} reaches for an HTTP client"


# --- Control 4: no write to memory-engine or perception-engine --------------


def test_control_4_the_only_repository_this_engine_writes_is_its_own() -> None:
    """Structural: with no cross-engine import and no HTTP client (control 3),
    and with `PUBLISHABLE_SUBJECTS` unchanged (control 1), there is no channel
    through which a write could reach either engine. This asserts the remaining
    one -- that no subject this engine may publish targets them."""
    for subject in PUBLISHABLE_SUBJECTS:
        assert not subject.startswith("memory."), subject
        assert not subject.startswith("perception."), subject


async def test_control_4_consuming_an_event_enqueues_nothing_for_publication() -> None:
    """The runtime half. A 4E handler that enqueued an outbox row could publish a
    side effect; none does."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from nova_contracts import (
        EventEnvelope,
        LongTermMemoryCreatedPayload,
        MemoryType,
        PrivacyLevel,
    )
    from nova_digital_twin_engine.events.handlers import make_memory_created_handler

    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = LongTermMemoryCreatedPayload(
        memory_id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        memory_type=MemoryType.PROJECT,
        importance_score=0.5,
        privacy_level=PrivacyLevel.INTERNAL,
        created_at=datetime.now(UTC),
    )

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            EventEnvelope(
                subject="memory.long_term.created",
                source_engine="memory-engine",
                correlation_id=uuid4(),
                payload=payload.model_dump(mode="json"),
            )
        )

    assert repository.outbox == []


# --- Control 7: only the five Sec7 routes are published ---------------------


_PHASE_4E_ROUTES = {
    ("GET", "/v1/digital-twin/domains"),
    ("GET", "/v1/digital-twin/domains/projects"),
    ("GET", "/v1/digital-twin/domains/projects/{project_id}"),
    ("GET", "/v1/digital-twin/domains/{domain}"),
    ("POST", "/v1/digital-twin/domains/{domain}/refresh"),
}

_SHIPPED_2DD_ROUTES = {
    ("GET", "/v1/digital-twin/profile"),
    ("PATCH", "/v1/digital-twin/profile"),
    ("GET", "/v1/digital-twin/preferences"),
    ("GET", "/v1/digital-twin/proactive-policy"),
    ("PATCH", "/v1/digital-twin/proactive-policy"),
    ("POST", "/v1/digital-twin/reset"),
}


def _published_routes() -> set[tuple[str, str]]:
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()
    return {
        (method.upper(), path)
        for path, operations in document["paths"].items()
        for method in operations
        if path.startswith("/v1/digital-twin")
    }


def test_control_7_the_openapi_document_publishes_exactly_five_new_routes() -> None:
    """**Sec14.5 control 7**, asserted against the served document rather than the
    router source -- what a caller can reach is what the document says, not what a
    decorator was meant to say."""
    published = _published_routes()

    assert published - _SHIPPED_2DD_ROUTES == _PHASE_4E_ROUTES
    assert len(_PHASE_4E_ROUTES) == 5


def test_control_7_the_three_2dd_route_groups_are_unchanged() -> None:
    """Sec7: *"existing routes are unchanged; these are additive."* Asserted so
    the additive claim is checkable rather than assumed."""
    assert _published_routes() >= _SHIPPED_2DD_ROUTES


def test_control_7_no_route_accepts_derived_domain_data() -> None:
    """A route that let a caller write a domain's facts would make every control
    here unprovable -- a fabricated value could enter through the front door. The
    only write takes a domain name and nothing else."""
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()

    for path, operations in document["paths"].items():
        if not path.startswith("/v1/digital-twin/domains"):
            continue
        for method, operation in operations.items():
            assert "requestBody" not in operation, (
                f"{method.upper()} {path} accepts a request body; 4E's write surface "
                "takes only which domain to re-derive"
            )


def test_control_7_4e_adds_no_internal_route_of_its_own() -> None:
    """Sec10 item 3, engine half.

    This engine *does* expose `/internal/health`, `/internal/readiness` and a
    mounted `/internal/metrics` -- every engine does, from `make_health_router`.
    The property 4E owns is that it added none: the internal surface is exactly
    what 2D-D shipped.
    """
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()

    internal = {p for p in document["paths"] if p.startswith("/internal")}
    assert internal == {"/internal/health", "/internal/readiness"}


def test_control_7_the_gateway_cannot_route_an_internal_path_at_all() -> None:
    """Sec10 item 3, gateway half -- where the property actually lives.

    `RouteTable` **raises at construction** for any prefix outside `/v1/`, and the
    forwarding router is mounted only on `/v1`. So there is no path from a browser
    to an engine's internal surface, and adding one would fail loudly rather than
    quietly widening the attack surface. Asserted against the real gateway class,
    because a check confined to this engine's document would miss a gateway change.
    """
    from nova_api_gateway.domain.routing import RouteTable, UpstreamRoute

    with pytest.raises(ValueError, match="must start with '/v1/'"):
        RouteTable(
            [
                UpstreamRoute(
                    prefix="/internal/metrics",
                    upstream_name="digital-twin-engine",
                    base_url="http://digital-twin-engine:8000",
                )
            ]
        )

    table = RouteTable(
        [
            UpstreamRoute(
                prefix="/v1/digital-twin",
                upstream_name="digital-twin-engine",
                base_url="http://digital-twin-engine:8000",
            )
        ]
    )
    assert table.resolve("/internal/metrics") is None
    assert table.resolve("/v1/digital-twin/domains") is not None


# --- Control 8: no autonomy subject, no autonomy behaviour ------------------


def test_control_8_no_autonomy_subject_is_registered_anywhere() -> None:
    assert [s for s in known_subjects() if s.startswith("autonomy.")] == []


def test_control_8_this_engine_declares_no_autonomy_subject() -> None:
    for subject in PUBLISHABLE_SUBJECTS | SUBSCRIBABLE_SUBJECTS:
        assert not subject.startswith("autonomy."), subject


def test_control_8_no_module_references_autonomy_in_executable_code() -> None:
    """Sec1.1: *"4E writes no policy, proposes no suggestion, and touches nothing
    in `autonomy-engine`."* AST-based, so the docstrings that explain the
    boundary do not trip the control that enforces it."""
    for path in _source_files():
        assert "autonomy" not in _code_of(path).lower(), (
            f"{path.name} references autonomy in executable code"
        )


# --- Control 9: CF-10 is not resolved by 4E (five sub-properties) -----------


def test_control_9a_no_trust_metric_rest_route() -> None:
    """Ratified Sec19.2, sub-property 1. `digital-twin-engine` owns `TrustMetric`
    and was open for extension here, which is exactly why this is asserted."""
    for _method, path in _published_routes():
        assert "trust" not in path.lower(), f"{path} exposes a trust surface"


def test_control_9b_no_trust_metric_event_bus_subject() -> None:
    """Sub-property 2."""
    for subject in PUBLISHABLE_SUBJECTS | SUBSCRIBABLE_SUBJECTS:
        assert "trust" not in subject.lower(), subject
    assert [s for s in known_subjects() if "trust" in s.lower()] == []


def test_control_9c_no_trust_metric_rpc_is_served() -> None:
    """Sub-property 3. `BoundEventBus.serve()` checks the *subscribable*
    allow-list, so a served trust RPC would have to appear there."""
    served = {s for s in SUBSCRIBABLE_SUBJECTS if s.endswith(".request")}
    assert served == {"digital_twin.preferences.get.request"}


def test_control_9d_the_autonomy_trust_adapter_is_byte_identical() -> None:
    """Sub-property 4. Compared by content hash against the file 4D shipped: 4E
    must not have touched `autonomy-engine`'s adapter, and a hash says so without
    depending on how the file is formatted."""
    import hashlib

    adapter = (
        _REPO_ROOT
        / "services"
        / "autonomy-engine"
        / "src"
        / "nova_autonomy_engine"
        / "clients"
        / "conversational_trust.py"
    )
    assert adapter.is_file(), "the 4D trust adapter is missing"
    digest = hashlib.sha256(adapter.read_bytes()).hexdigest()
    assert digest == _TRUST_ADAPTER_SHA256, (
        "autonomy-engine's conversational trust adapter changed. CF-10 stays OPEN "
        "in 4E (ratified Sec19.2): if this is a deliberate later-milestone change, "
        "the carry-forward is being closed and that needs its own decision."
    )


_TRUST_ADAPTER_SHA256 = "0175e11fb9a6e5db042a118bb3ffce769625bafd75abb22298499c9e8af9039b"
"""`services/autonomy-engine/src/nova_autonomy_engine/clients/conversational_trust.py`.

Computed from the file, and separately verified equal to
`git show 68397a2:<that path> | sha256sum` -- the Phase 4D merge commit -- so this
pins the adapter to what 4D shipped rather than to whatever happened to be on disk
when this test was written."""


def test_control_9e_fail_closed_trust_behaviour_is_unchanged() -> None:
    """Sub-property 5, asserted behaviourally rather than by inspection: `score`
    is `None` and never `0.0`, and `satisfies_threshold(None, t)` is `False` for
    every `t` **including `0.0`**.

    Zero corrections would read as *perfect* trust, so a `None` that degraded to
    `0.0` would not fail loudly -- it would silently authorise. That is why this
    is checked at every threshold rather than at a representative one.
    """
    from nova_autonomy_engine.domain.trust import satisfies_threshold

    for threshold in (0.0, 0.1, 0.5, 0.9, 1.0):
        assert satisfies_threshold(None, threshold) is False, threshold


# --- Control 10: every non-populated state carries a reason -----------------


def test_control_10_is_enforced_by_the_type_not_only_by_a_test() -> None:
    """The control's strongest form. `tests/unit/test_domain_model_invariants.py`
    drives each forbidden construction; this asserts that the validator enforcing
    them still exists, so deleting it fails here too rather than quietly turning
    ten controls into documentation."""
    from nova_digital_twin_engine.domain.models import DomainModel

    validators = ast.parse(
        (_SOURCE_ROOT / "domain" / "models.py").read_text()
    )
    names = {
        node.name
        for node in ast.walk(validators)
        if isinstance(node, ast.FunctionDef)
    }
    assert "_state_is_supported_by_its_evidence" in names
    assert "_respects_the_ratified_per_domain_floor" in names
    assert DomainModel.model_config.get("extra") is None  # no silent-accept mode


def test_control_7_no_route_accepts_a_user_id_parameter() -> None:
    """ADR-025 and Sec10 item 1: **4E introduces no second identity concept.**

    The identity is `settings.primary_user_id`, resolved server-side, the same
    way `/v1/autonomy/*` resolves it. A `user_id` parameter would put a selection
    at the edge that the system cannot honour -- there is one user -- and would
    read like multi-tenancy this architecture does not have.
    """
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()

    for path, operations in document["paths"].items():
        if not path.startswith("/v1/digital-twin/domains"):
            continue
        for method, operation in operations.items():
            names = {p["name"] for p in operation.get("parameters", [])}
            assert "user_id" not in names, f"{method.upper()} {path} takes a user_id"


# --- Finding 3: what the D-6 prefix exposes, and on what identity terms ------


def test_finding_3_the_prefix_exposes_exactly_these_six_pre_4e_operations() -> None:
    """**The engine-side half of finding 3's regression guard.**

    `api-gateway` fronts `/v1/digital-twin` as one prefix (D-6, forwarded 1:1),
    so *every* operation under it is externally reachable -- including Phase
    2D-D's six, which were unreachable before 4E because no panel read them and
    no gateway entry existed.

    That is D-6's mechanism working, identically to `/v1/agents` fronting the
    Kernel's whole subtree, and the alternatives are the two D-6 rejected: exact
    -path entries that drift from the engine, or a rewriting layer. So the
    behaviour is kept and pinned rather than worked around.

    Pinned here as well as in `api-gateway`'s own test because this is the side
    that can *grow*: a seventh 2D-D-shaped route added to this engine later
    becomes externally reachable the moment it exists, with no gateway change to
    notice it by. This test is that notice.
    """
    assert _published_routes() - _PHASE_4E_ROUTES == _SHIPPED_2DD_ROUTES
    assert len(_SHIPPED_2DD_ROUTES) == 6


def test_finding_3_only_the_pre_4e_operations_take_a_caller_supplied_user_id() -> None:
    """The asymmetry finding 3 names, asserted rather than described.

    4E's five resolve `primary_user_id` server-side (ADR-025, Sec10 item 1).
    2D-D's six take it as a **required query parameter**, and three of them
    write -- `PATCH /profile`, `PATCH /proactive-policy`, `POST /reset`.

    **Not a confidentiality vector today**: one trusted user per instance, so
    there is no second user's data to address, and D-3 authenticates every
    request before any upstream call is made. It is an identity-at-the-edge
    surface, an integrity surface (rows keyed to an arbitrary UUID nothing
    reads), and a real hazard if ADR-025 is ever relaxed.

    **Reported, not fixed** (protocol Sec13.1): moving 2D-D's routes to
    server-side identity changes shipped behaviour and desynchronises them from
    `digital_twin.preferences.get.request`, which carries `user_id` on the wire
    by design. This test records the state so the decision is taken explicitly
    rather than inherited.
    """
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()

    takes_user_id: set[tuple[str, str]] = set()
    for path, operations in document["paths"].items():
        if not path.startswith("/v1/digital-twin"):
            continue
        for method, operation in operations.items():
            names = {
                p["name"] for p in operation.get("parameters", []) if p.get("in") == "query"
            }
            if "user_id" in names:
                takes_user_id.add((method.upper(), path))

    assert takes_user_id == _SHIPPED_2DD_ROUTES, (
        "the set of digital-twin operations taking a caller-supplied user_id "
        "changed. If a 4E route acquired one, that breaks Sec10 item 1; if a 2D-D "
        "route lost one, finding 3 is being resolved and its record in "
        "api-gateway's domain/routing.py needs updating with it."
    )
