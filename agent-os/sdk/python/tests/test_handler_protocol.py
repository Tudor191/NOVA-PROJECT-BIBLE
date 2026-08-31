"""Tests for the `AgentHandler` Protocol (doc 12 §4, verbatim method set)."""

from __future__ import annotations

import inspect

from nova_agent_sdk import AgentHandler


def test_agent_handler_declares_doc12_section4_verbatim_method_set() -> None:
    expected_methods = {
        "on_load",
        "on_unload",
        "on_assign",
        "execute",
        "on_pause",
        "on_resume",
        "self_validate",
        "health_check",
        "on_message",
        "metrics_snapshot",
    }
    declared = {
        name
        for name, _ in inspect.getmembers(AgentHandler)
        if not name.startswith("_") and name in expected_methods
    }
    assert declared == expected_methods


def test_agent_handler_is_runtime_checkable() -> None:
    # A bare object satisfying none of the methods must not accidentally
    # match -- confirms `@runtime_checkable` structural checking is live,
    # not silently bypassed.
    assert not isinstance(object(), AgentHandler)
