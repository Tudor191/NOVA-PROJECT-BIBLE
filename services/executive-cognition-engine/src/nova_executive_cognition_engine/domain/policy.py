"""Executive policies (docs/design/phase-2c/00-executive-cognition-engine.md
§12) -- fixed, named, structural rules, never learned or inferred.
`Settings`-configured, not database-stored (a small, fixed policy set
doesn't yet need the CRUD surface a database table would imply, mirroring
Reasoning Engine's own `confidence_verify_threshold` convention).

Epistemic deference (ADR-028, design doc §0.5) is deliberately not a fifth
entry in `DEFAULT_POLICIES` -- it is a hard, non-overridable structural
invariant enforced directly in `conflict_resolution.py`, never something a
policy configuration could disable (§12's own closing note).

`privacy_overrides_convenience` has no corresponding runtime branch in
`arbitration.py`/`conflict_resolution.py`: this engine never constructs a
new copy of a request's content, only reads and scores what it's given, so
there is structurally no code path where it could lower a declared privacy
tier to make arbitration more convenient. Listed here for explainability
completeness (§16) and parity with Part 19's own four named examples, not
because it needs enforcement logic. `critical_alerts_override_focus_mode`
is out of scope this phase (§12 point 4, §5.12) -- no "focus mode" concept
exists without Communication Engine -- and is intentionally absent from
`DEFAULT_POLICIES` rather than included as an inert placeholder.
"""

from __future__ import annotations

from nova_executive_cognition_engine.domain.models import ExecutivePolicy

__all__ = ["DEFAULT_POLICIES"]

DEFAULT_POLICIES: tuple[ExecutivePolicy, ...] = (
    ExecutivePolicy(
        name="user_goals_override_optimization",
        description=(
            "A request tied to an explicit, active user goal is never WAIT-ed behind "
            "a background/no-goal request, regardless of composite score."
        ),
        applies_to="arbitration",
    ),
    ExecutivePolicy(
        name="safety_overrides_speed",
        description=(
            "A request at or above the high-risk threshold is never PROCEED_REDUCED; "
            "it receives its full requested budget or WAITs, never a degraded "
            "allocation that could compound the risk."
        ),
        applies_to="both",
    ),
    ExecutivePolicy(
        name="privacy_overrides_convenience",
        description=(
            "This engine never lowers a request's declared privacy tier to make "
            "arbitration more convenient -- structurally true by construction; "
            "no runtime check corresponds to this policy."
        ),
        applies_to="both",
    ),
)
