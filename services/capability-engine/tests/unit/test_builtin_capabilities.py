"""`build_builtin_manifests` -- the four Phase 3 built-ins (TDD 3C §0)."""

from __future__ import annotations

from nova_capability_engine.domain.builtin_capabilities import build_builtin_manifests


def test_builds_exactly_the_four_named_built_ins() -> None:
    manifests = build_builtin_manifests(
        filesystem_root="/workspace",
        terminal_allowed_executables=["git", "python3"],
        http_allowed_hosts=["api.example.com"],
    )

    names = {m.name for m in manifests}
    assert names == {"filesystem", "terminal", "git", "http"}
    assert {m.execution_adapter for m in manifests} == names


def test_required_resources_are_deployment_scoped_from_settings() -> None:
    manifests = build_builtin_manifests(
        filesystem_root="/custom/root",
        terminal_allowed_executables=["only-this-one"],
        http_allowed_hosts=["only.example.com"],
    )
    by_name = {m.name: m for m in manifests}

    assert by_name["filesystem"].required_resources == ["/custom/root"]
    assert by_name["git"].required_resources == ["/custom/root"]
    assert by_name["terminal"].required_resources == ["only-this-one"]
    assert by_name["http"].required_resources == ["only.example.com"]


def test_none_declare_a_dependency() -> None:
    manifests = build_builtin_manifests(
        filesystem_root="/workspace", terminal_allowed_executables=[], http_allowed_hosts=[]
    )
    assert all(m.dependencies == [] for m in manifests)
