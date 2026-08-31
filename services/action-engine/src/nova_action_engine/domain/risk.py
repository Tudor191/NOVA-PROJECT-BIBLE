"""Risk classification for an `Action` (TDD 3D §6 stage 4, Bible Part 14's
`RiskLevel` scale, reused). No document in this project specifies the
exact classification rule from `(action_type, operation)` to `RiskLevel`
-- unlike `execution_target`/idempotency (`13-3d-action-engine-research.md`
§5.1/§5.3), this gap was not surfaced during the Phase 3D research pass and
is not one of the three approved decisions. **Disclosed here, not silently
invented**: a small, deterministic, minimal classifier, proposed and
flagged for future refinement -- not a competing architecture (no
alternative classification scheme is proposed anywhere in this project's
documents), so implemented directly rather than escalated, per this
project's own "small implementation-time precision, not a fork" idiom
already used for e.g. Fork 3C-4's idempotency mechanism before it was
elevated to a fork.

Bible's own Safety Layers examples (`part-12-action-engine.md:453-471`:
delete files, format storage, credential modification, ...) anchor the
`critical` tier -- including TDD 3D §14's own named acceptance-criterion
scenario, a filesystem delete."""

from __future__ import annotations

from nova_contracts import RiskLevel

__all__ = ["classify_risk"]

_CRITICAL_OPERATIONS = frozenset({"delete", "remove", "format"})
_HIGH_RISK_OPERATIONS = frozenset({"execute"})
_MODERATE_RISK_OPERATIONS = frozenset({"write"})


def classify_risk(*, action_type: str, operation: str) -> RiskLevel:
    op = operation.strip().lower()
    if op in _CRITICAL_OPERATIONS:
        return RiskLevel.CRITICAL
    if action_type == "terminal" and op in _HIGH_RISK_OPERATIONS:
        return RiskLevel.HIGH
    if op in _MODERATE_RISK_OPERATIONS:
        return RiskLevel.MODERATE
    if op in {"read", "list", "status", "log", "diff"}:
        return RiskLevel.NEGLIGIBLE
    return RiskLevel.LOW
