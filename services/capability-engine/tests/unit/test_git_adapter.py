"""`GitAdapter` -- real `git` subprocess calls against a real throwaway repo
in `tmp_path`, composing `TerminalAdapter.run_subprocess` directly. Real,
adversarial sandbox-escape attempts, never mocked."""

from __future__ import annotations

import subprocess

import pytest
from nova_capability_engine.adapters.git_adapter import GitAdapter
from nova_capability_engine.domain.sandbox import SandboxViolation


@pytest.fixture
def repo(tmp_path):  # type: ignore[no-untyped-def]
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    return tmp_path


async def test_status_on_a_real_repo_succeeds(repo) -> None:  # type: ignore[no-untyped-def]
    adapter = GitAdapter()

    result = await adapter.invoke("status", {}, required_resources=[str(repo)])

    assert result["exit_code"] == 0


async def test_add_and_commit_round_trip_on_a_real_repo(repo) -> None:  # type: ignore[no-untyped-def]
    (repo / "file.txt").write_text("content")
    adapter = GitAdapter()

    add_result = await adapter.invoke(
        "add", {"args": ["file.txt"]}, required_resources=[str(repo)]
    )
    assert add_result["exit_code"] == 0

    commit_result = await adapter.invoke(
        "commit", {"args": ["-m", "test commit"]}, required_resources=[str(repo)]
    )
    assert commit_result["exit_code"] == 0

    log_result = await adapter.invoke("log", {}, required_resources=[str(repo)])
    assert "test commit" in log_result["stdout"]


async def test_a_disallowed_subcommand_is_a_real_blocked_sandbox_violation(repo) -> None:  # type: ignore[no-untyped-def]
    adapter = GitAdapter()

    with pytest.raises(SandboxViolation) as exc_info:
        await adapter.invoke("push", {"args": ["origin", "main"]}, required_resources=[str(repo)])
    assert exc_info.value.adapter == "git"


async def test_a_repo_root_outside_the_declared_resources_is_a_real_blocked_sandbox_violation(
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    declared_root = tmp_path / "declared"
    declared_root.mkdir()
    other_repo = tmp_path / "other"
    other_repo.mkdir()
    subprocess.run(["git", "init"], cwd=other_repo, check=True, capture_output=True)
    adapter = GitAdapter()

    with pytest.raises(SandboxViolation):
        await adapter.invoke(
            "status", {"repo_root": str(other_repo)}, required_resources=[str(declared_root)]
        )
