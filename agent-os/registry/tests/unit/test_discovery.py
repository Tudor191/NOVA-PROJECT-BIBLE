"""`discover_agent_packages` -- doc 12 §6/§15's filesystem-based
discovery: every immediate subdirectory of `agents_root` with both
`agent.yaml` and `src/handler.py` present."""

from __future__ import annotations

from pathlib import Path

from nova_agent_os_registry.domain.discovery import DiscoveredPackage, discover_agent_packages


def test_returns_empty_list_when_agents_root_does_not_exist(tmp_path: Path) -> None:
    assert discover_agent_packages(tmp_path / "does-not-exist") == []


def test_returns_empty_list_for_an_empty_agents_root(tmp_path: Path) -> None:
    assert discover_agent_packages(tmp_path) == []


def test_skips_a_directory_missing_agent_yaml(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete-agent"
    (incomplete / "src").mkdir(parents=True)
    (incomplete / "src" / "handler.py").write_text("class Handler: ...\n")

    assert discover_agent_packages(tmp_path) == []


def test_skips_a_directory_missing_handler_py(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete-agent"
    incomplete.mkdir()
    (incomplete / "agent.yaml").write_text("id: incomplete-agent\n")

    assert discover_agent_packages(tmp_path) == []


def test_skips_files_directly_under_agents_root(tmp_path: Path) -> None:
    (tmp_path / "not-a-directory.txt").write_text("stray file")

    assert discover_agent_packages(tmp_path) == []


def test_discovers_a_complete_package(tmp_path: Path) -> None:
    complete = tmp_path / "coding-agent"
    (complete / "src").mkdir(parents=True)
    manifest_path = complete / "agent.yaml"
    handler_path = complete / "src" / "handler.py"
    manifest_path.write_text("id: coding-agent\n")
    handler_path.write_text("class Handler: ...\n")

    discovered = discover_agent_packages(tmp_path)

    assert discovered == [
        DiscoveredPackage(
            directory=complete, manifest_path=manifest_path, handler_path=handler_path
        )
    ]


def test_discovers_multiple_packages_in_sorted_order(tmp_path: Path) -> None:
    for name in ("coding-agent", "browser-agent", "devops-agent"):
        package_dir = tmp_path / name
        (package_dir / "src").mkdir(parents=True)
        (package_dir / "agent.yaml").write_text(f"id: {name}\n")
        (package_dir / "src" / "handler.py").write_text("class Handler: ...\n")

    discovered = discover_agent_packages(tmp_path)

    assert [package.directory.name for package in discovered] == [
        "browser-agent",
        "coding-agent",
        "devops-agent",
    ]
