"""Guards for the local stack's one-shot schema migrator.

`infra/docker/run-migrations.sh` carries a hand-maintained table of
`(engine directory, settings env prefix)` pairs, and
`docker-compose.local.yml` carries a hand-maintained set of
`depends_on: migrations` gates. Both drift silently: an engine added to
compose but not to the script starts against a database with no schema for
it, which is exactly the crash loop the migrator exists to prevent, and an
engine whose `env_prefix` changes gets migrated at alembic's `localhost`
default instead of the compose database.

Neither failure is visible without actually running the stack, and running
the stack is the expensive path (Docker, CI-only). These tests make both
cheap and unmissable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.local.yml"
SCRIPT = REPO_ROOT / "infra" / "docker" / "run-migrations.sh"


def _script_engines() -> list[tuple[str, str]]:
    """The `(directory, env prefix)` pairs the migrator will actually run."""
    block = re.search(r"ENGINES=\(\n(.*?)\n\)", SCRIPT.read_text(), re.S)
    assert block is not None, "could not find the ENGINES array in run-migrations.sh"
    pairs = re.findall(r'"([^:"]+):([^"]+)"', block.group(1))
    assert pairs, "the ENGINES array parsed as empty; fix this parser, do not delete it"
    return pairs


def _compose_services() -> dict[str, dict]:
    return yaml.safe_load(COMPOSE.read_text())["services"]


def _environment(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        return dict(item.split("=", 1) for item in env if "=" in item)
    return env


def _postgres_backed(services: dict[str, dict]) -> dict[str, str]:
    """Compose service -> the `*_POSTGRES_DSN` key it configures."""
    found = {}
    for name, cfg in services.items():
        for key in _environment(cfg):
            if key.endswith("POSTGRES_DSN"):
                found[name] = key
    return found


def _depends_on_migrations(service: dict) -> str | None:
    depends = service.get("depends_on")
    if isinstance(depends, dict):
        entry = depends.get("migrations")
        return entry.get("condition") if isinstance(entry, dict) else None
    return None


# --- the script's table matches reality -------------------------------------


@pytest.mark.parametrize(("directory", "prefix"), _script_engines())
def test_each_migrated_engine_has_an_alembic_config(directory: str, prefix: str) -> None:
    ini = REPO_ROOT / directory / "alembic.ini"
    assert ini.is_file(), f"{directory} is in the migrator's list but has no alembic.ini"
    assert prefix.endswith("_"), f"{prefix!r} must end with '_' to form {prefix}POSTGRES_DSN"


@pytest.mark.parametrize(("directory", "prefix"), _script_engines())
def test_env_prefix_matches_the_engines_own_settings(directory: str, prefix: str) -> None:
    """The prefix is *not* derivable from the directory name by contract.

    It happens to be a mechanical transform for all thirteen today. Asserting
    it against each engine's own `SettingsConfigDict(env_prefix=...)` is what
    keeps that a coincidence rather than an assumption -- an engine that adopts
    a different prefix fails here instead of silently migrating nothing.
    """
    configs = list((REPO_ROOT / directory / "src").rglob("config.py"))
    assert configs, f"{directory} has no config.py"
    match = re.search(r'env_prefix="([^"]*)"', configs[0].read_text())
    assert match is not None, f"{configs[0]} declares no env_prefix"
    assert match.group(1) == prefix, (
        f"{directory}: run-migrations.sh says {prefix!r}, config.py says "
        f"{match.group(1)!r}. The migrator would connect to alembic's "
        "localhost default and migrate nothing."
    )


# --- compose and the script agree -------------------------------------------


def test_every_postgres_backed_service_waits_for_migrations() -> None:
    services = _compose_services()
    ungated = {
        name: _depends_on_migrations(cfg)
        for name, cfg in services.items()
        if name != "migrations" and name in _postgres_backed(services)
        and _depends_on_migrations(cfg) != "service_completed_successfully"
    }
    assert not ungated, (
        f"Postgres-backed services not gated on the migrator: {ungated}. "
        "Each needs `depends_on: {migrations: {condition: "
        "service_completed_successfully}}` or it starts against an unmigrated "
        "database."
    )


def test_every_postgres_backed_service_is_covered_by_the_migrator() -> None:
    """Compose may not run an engine whose schema nothing creates."""
    services = _compose_services()
    migrated_dirs = {directory for directory, _ in _script_engines()}
    migrated_names = {Path(d).name for d in migrated_dirs}

    uncovered = sorted(
        name
        for name in _postgres_backed(services)
        # The migrator itself carries a DSN (`NOVA_POSTGRES_DSN`) precisely
        # because it is the thing that runs the migrations.
        if name != "migrations"
        # `<engine>-worker` siblings share their engine's schema and DSN.
        and name.removesuffix("-worker") not in migrated_names
    )
    assert not uncovered, (
        f"Postgres-backed compose services with no migration: {uncovered}. "
        "Add each to the ENGINES array in infra/docker/run-migrations.sh."
    )


def test_the_migrator_does_not_wait_for_itself() -> None:
    migrations = _compose_services()["migrations"]
    assert _depends_on_migrations(migrations) is None
    assert (migrations.get("depends_on") or {}).get("postgres", {}).get(
        "condition"
    ) == "service_healthy"


def test_the_migrator_is_not_restarted_after_it_exits() -> None:
    """`service_completed_successfully` depends on the container staying dead.

    A `restart: unless-stopped` here (the value every other service in this
    file uses) would resurrect the migrator after its successful exit.
    """
    assert _compose_services()["migrations"]["restart"] == "no"


# --- anti-decoration controls -----------------------------------------------


def test_the_parsers_actually_found_something() -> None:
    """Every assertion above is vacuous if these parse to empty."""
    assert len(_script_engines()) >= 10
    services = _compose_services()
    assert len(_postgres_backed(services)) >= 10
    assert "migrations" in services
