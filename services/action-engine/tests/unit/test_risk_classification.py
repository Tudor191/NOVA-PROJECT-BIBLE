"""`domain.risk.classify_risk` -- the small, deterministic, disclosed
default classifier (`domain/risk.py`'s own module docstring: no document in
this project specifies the exact `(action_type, operation) -> RiskLevel`
mapping)."""

from __future__ import annotations

from nova_action_engine.domain.risk import classify_risk
from nova_contracts import RiskLevel


def test_delete_is_always_critical_regardless_of_action_type() -> None:
    assert classify_risk(action_type="filesystem", operation="delete") is RiskLevel.CRITICAL
    assert classify_risk(action_type="terminal", operation="remove") is RiskLevel.CRITICAL
    assert classify_risk(action_type="filesystem", operation="format") is RiskLevel.CRITICAL


def test_terminal_execute_is_high_risk() -> None:
    assert classify_risk(action_type="terminal", operation="execute") is RiskLevel.HIGH


def test_filesystem_execute_is_not_high_risk() -> None:
    """`execute` is only elevated to HIGH for `terminal` actions -- a
    `filesystem` capability has no `execute` operation in practice, but the
    classifier's own rule is action-type-scoped, not operation-name-only."""
    assert classify_risk(action_type="filesystem", operation="execute") is not RiskLevel.HIGH


def test_write_is_moderate_risk() -> None:
    assert classify_risk(action_type="filesystem", operation="write") is RiskLevel.MODERATE


def test_read_like_operations_are_negligible_risk() -> None:
    for operation in ("read", "list", "status", "log", "diff"):
        assert classify_risk(action_type="filesystem", operation=operation) is RiskLevel.NEGLIGIBLE


def test_unrecognized_operation_defaults_to_low_risk() -> None:
    assert classify_risk(action_type="filesystem", operation="unknown_op") is RiskLevel.LOW


def test_operation_matching_is_case_and_whitespace_insensitive() -> None:
    assert classify_risk(action_type="filesystem", operation="  DELETE  ") is RiskLevel.CRITICAL
