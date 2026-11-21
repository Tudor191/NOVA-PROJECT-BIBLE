"""The acceptance-only compose override stays exactly what was ratified, and
stays out of everything else (TDD 4F.8 §28.7 option (B), §29.2; D8).

`infra/docker/docker-compose.acceptance.yml` runs `nova-companion` under a
distinct non-root uid with the CI runner's gid. So AC-7's revocation,
`chmod g-rx` on the shared workspace, withdraws the sensor's permission and not
`capability-engine`'s (F-4F8-13). The ratification fixed four properties, and
each is pinned here:

1. the override sets **exactly one key on exactly one service**:
   `nova-companion.user`;
2. its uid is **non-root, and not 1000**, which `capability-engine` runs as;
3. the companion **Dockerfile's runtime user is unchanged**, and the base
   compose gives the companion no `user:`, so the production deployment model
   is untouched;
4. **no other step or compose file uses the override**. Exactly one workflow
   step applies it, the acceptance `up` of the P8 services.

Parsed with `yaml`, never executed.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERRIDE = REPO_ROOT / "infra" / "docker" / "docker-compose.acceptance.yml"
BASE = REPO_ROOT / "infra" / "docker" / "docker-compose.local.yml"
COMPANION_DOCKERFILE = REPO_ROOT / "companion" / "nova-companion" / "Dockerfile"
CAPABILITY_DOCKERFILE = REPO_ROOT / "services" / "capability-engine" / "Dockerfile"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
OVERRIDE_NAME = OVERRIDE.name
P8_STEP = "Start the P8 services (perception-engine, its worker, nova-companion)"

_USER = re.compile(r"^(?P<uid>\d+):\$\{NOVA_ACCEPTANCE_COMPANION_GID:\?[^}]+\}$")


def _override() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(OVERRIDE.read_text())


def _useradd_uid(dockerfile: Path) -> int:
    match = re.search(r"useradd [^\n]*--uid (\d+)", dockerfile.read_text())
    assert match, f"{dockerfile.relative_to(REPO_ROOT)} creates no user with --uid"
    return int(match.group(1))


def test_the_override_sets_exactly_one_key_on_exactly_one_service() -> None:
    override = _override()
    assert set(override) == {"services"}, override
    assert set(override["services"]) == {"nova-companion"}, override
    assert set(override["services"]["nova-companion"]) == {"user"}, override


def test_the_companion_uid_is_non_root_and_not_capability_engines() -> None:
    user = _override()["services"]["nova-companion"]["user"]
    match = _USER.match(user)
    assert match, (
        f"user must be '<uid>:${{NOVA_ACCEPTANCE_COMPANION_GID:?...}}', refusing to "
        f"start without the runner's gid; found {user!r}"
    )
    uid = int(match.group("uid"))
    assert uid != 0, "the acceptance companion must not run as root"
    assert uid != _useradd_uid(CAPABILITY_DOCKERFILE) == 1000, (
        "the companion must not share capability-engine's uid, or a revocation of "
        "the shared workspace revokes both (F-4F8-13)"
    )
    assert uid != _useradd_uid(COMPANION_DOCKERFILE)


def test_the_production_deployment_model_is_unchanged() -> None:
    dockerfile = COMPANION_DOCKERFILE.read_text()
    assert _useradd_uid(COMPANION_DOCKERFILE) == 1000
    assert re.search(r"^USER nova$", dockerfile, re.MULTILINE), (
        "the companion image's runtime user changed"
    )
    base = yaml.safe_load(BASE.read_text())["services"]["nova-companion"]
    assert "user" not in base, "the base compose now overrides the companion's user"


def test_exactly_one_workflow_step_applies_the_override() -> None:
    users = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        jobs = (yaml.safe_load(workflow.read_text()) or {}).get("jobs", {})
        for job_name, job in jobs.items():
            for step in job.get("steps", []):
                if OVERRIDE_NAME in str(step.get("run", "")):
                    users.append((workflow.name, job_name, step.get("name")))
    assert users == [("pr-checks.yml", "e2e", P8_STEP)], users


def test_the_applying_step_derives_the_gid_from_the_runner() -> None:
    jobs = yaml.safe_load((WORKFLOWS / "pr-checks.yml").read_text())["jobs"]
    (step,) = [s for s in jobs["e2e"]["steps"] if s.get("name") == P8_STEP]
    script = step["run"]
    assert 'NOVA_ACCEPTANCE_COMPANION_GID="$(id -g)"' in script
    assert f"-f infra/docker/docker-compose.local.yml -f infra/docker/{OVERRIDE_NAME}" in script


def test_no_other_compose_file_or_script_names_the_override() -> None:
    """Outside workflows, only the override itself may name it."""
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for root in (REPO_ROOT / "infra", REPO_ROOT / "tools")
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".yml", ".yaml", ".sh", ".py"}
        and path != OVERRIDE
        and path != Path(__file__).resolve()
        and OVERRIDE_NAME in path.read_text(errors="ignore")
    ]
    assert not offenders, offenders
