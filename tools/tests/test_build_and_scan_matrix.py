"""Guard for `build-and-scan.yml`'s hand-maintained image matrix.

Every other hand-maintained CI list in this repository already has one --
`test_compose_migrations.py` for the migrator's `ENGINES` array,
`test_e2e_stack_completeness.py` for the e2e job's service list,
`test_worker_queue_isolation.py` for the per-service queue names. The Docker
matrix was the last one without, and it is the one whose drift is least
visible: an image absent from the matrix is simply never built and never
CVE-scanned, and nothing anywhere reports its absence.

Phase 3E is the concrete precedent. Its own condition C-3 recorded that
`agent-os` had "no Dockerfile, no compose service, no `build-and-scan` matrix
entry, and therefore no Trivy scan" -- a gap that survived a full phase and a
Gate Review, and that the protocol (§9.2) now names explicitly as something a
phase making an `agent-os` component deployable must close. Phase 4C's 4C.1
closes it; this file keeps it closed.

The matrix also stopped being derivable from the service name in 4C.1: it was
a flat list built as `services/<name>/Dockerfile`, and the three `agent-os`
images live elsewhere. The path is now carried per entry, which is one more
thing that can silently disagree with the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-and-scan.yml"

#: Dockerfiles that deliberately ship no scanned image, each with the reason.
#: A path may only be added here with one -- "not scanned" is a decision, not
#: an oversight.
UNSCANNED = {
    "infra/docker/Dockerfile.migrations": (
        "the one-shot schema migrator: it runs to completion and exits, exposes "
        "no port, serves no traffic, and nothing depends on it at runtime. "
        "Stated in its own header rather than left to look like an oversight."
    ),
}


def _matrix_entries() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    include = workflow["jobs"]["build-and-scan"]["strategy"]["matrix"]["include"]
    assert include, "the build-and-scan matrix parsed as empty; fix this parser"
    return include


def _repo_dockerfiles() -> set[str]:
    """Every Dockerfile in the repository, as a repo-relative POSIX path."""
    found = {
        str(path.relative_to(REPO_ROOT).as_posix())
        for path in REPO_ROOT.rglob("Dockerfile*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".venv" not in path.parts
        and ".git" not in path.parts
    }
    assert found, "found no Dockerfiles at all; fix this parser, do not delete it"
    return found


@pytest.mark.parametrize("entry", _matrix_entries(), ids=lambda e: e["service"])
def test_every_matrix_entry_points_at_a_real_dockerfile(entry: dict) -> None:
    dockerfile = entry.get("dockerfile")
    assert dockerfile, f"matrix entry {entry['service']!r} declares no dockerfile path"
    assert (REPO_ROOT / dockerfile).is_file(), (
        f"matrix entry {entry['service']!r} builds {dockerfile!r}, which does not "
        f"exist. The job would fail on every run."
    )


def test_every_dockerfile_is_either_scanned_or_deliberately_excluded() -> None:
    """The direction that actually catches a missed image.

    The test above catches a matrix entry with no file. This one catches a
    file with no matrix entry -- which is the Phase 3E failure: three
    components that could have been built and scanned, and were not, for a
    whole phase.
    """
    in_matrix = {entry["dockerfile"] for entry in _matrix_entries()}
    unscanned = _repo_dockerfiles() - in_matrix - set(UNSCANNED)
    assert not unscanned, (
        f"Dockerfiles built by nothing and CVE-scanned by nothing: "
        f"{sorted(unscanned)}. Add each to build-and-scan.yml's matrix, or to "
        f"this file's UNSCANNED map with the reason it ships no image."
    )


def test_matrix_service_names_are_unique() -> None:
    """The name keys the image tag and the build cache scope, so a duplicate
    would have two jobs overwriting one another's cache under one tag."""
    names = [entry["service"] for entry in _matrix_entries()]
    assert len(names) == len(set(names)), f"duplicate matrix service names in {names}"


# --- controls: these parsers must fail loudly, never silently pass -----------


def test_the_parsers_found_the_known_matrix() -> None:
    """Every assertion above is vacuous if these parse to junk."""
    names = {entry["service"] for entry in _matrix_entries()}
    for expected in ("nova-core", "communication-engine", "api-gateway", "ws-gateway"):
        assert expected in names, f"the parsed matrix is missing {expected!r}"
    assert len(_repo_dockerfiles()) >= len(names)


def test_all_three_agent_os_components_are_scanned() -> None:
    """Phase 4C's D-5, named rather than left to the general rule above.

    These three had never been built or CVE-scanned in the project's history
    (Phase 3E condition C-3). If they ever drop out of the matrix, the general
    rule would catch it -- but this test says which criterion regressed.
    """
    by_name = {entry["service"]: entry["dockerfile"] for entry in _matrix_entries()}
    assert by_name.get("agent-os-kernel") == "agent-os/kernel/Dockerfile"
    assert by_name.get("agent-os-registry") == "agent-os/registry/Dockerfile"
    assert by_name.get("agent-os-supervisors") == "agent-os/supervisors/Dockerfile"
