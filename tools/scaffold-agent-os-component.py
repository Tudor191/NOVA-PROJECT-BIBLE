#!/usr/bin/env python3
"""Generate a new `agent-os/<name>` component (Fork 3E-4, resolved:
docs/design/phase-3/08-tdd-3e-agent-os.md §3, §11) -- distinct from
`tools/scaffold-engine.py` because `agent-os/` is not the standard engine
template (docs/architecture/02-repository-and-folder-structure.md:53-65,
`01-tdd-preparation-and-fork-resolutions.md` §5.3): no `-engine` suffix,
no `/v1/...` REST surface, and health/readiness come from
`nova-service-kit`'s `make_health_router()` (unmodified reuse, TDD 3E §4)
rather than a hand-rolled per-component `api/health.py`.

Usage:
    uv run python tools/scaffold-agent-os-component.py <name>   # e.g. kernel

The generated component boots (FastAPI + lifespan-managed EventBus connection),
exposes `/internal/health`, `/internal/readiness` (via `make_health_router()`)
and `/internal/metrics` (via `prometheus_asgi_app()`, the same two-helper
pairing every one of the 10 conforming engines already uses -- confirmed by
grep, `services/memory-engine/src/nova_memory_engine/main.py:184-187`), and
declares empty publish/subscribe allow-lists ready for its author to fill in.
It deliberately does NOT generate a Dockerfile or wire itself into
docker-compose.local.yml / build-and-scan.yml's matrix -- doc 02 is explicit
that `agent-os/kernel` is control-plane infrastructure, not automatically "an
instance of the standard engine template", and `01-tdd-preparation-and-
fork-resolutions.md` §5.2 lists container-image wiring as conditional ("if it
ships as its own container image"), not automatic like every `-engine`. That
wiring is a separate, deliberate follow-up step once a component is actually
ready to be deployed as its own container -- not invented here.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import tomlkit

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_OS_DIR = REPO_ROOT / "agent-os"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
PNPM_WORKSPACE = REPO_ROOT / "pnpm-workspace.yaml"

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_WORKSPACE_GLOB = "agent-os/*"


def _validate_name(name: str) -> None:
    if not _NAME_PATTERN.match(name):
        raise SystemExit(
            f"Invalid agent-os component name {name!r}. Expected kebab-case, "
            f"e.g. 'kernel' or 'registry' (no '-engine' suffix requirement -- "
            f"Fork 3E-4)."
        )
    if (AGENT_OS_DIR / name).exists():
        raise SystemExit(f"agent-os/{name} already exists.")


def _module_name(name: str) -> str:
    # "nova_agent_os_" prefix -- every other workspace module is "nova_"-
    # prefixed (nova_core, nova_planning_engine, ...); disambiguates from a
    # future bare "nova_kernel" and satisfies `01-tdd-preparation-and-fork-
    # resolutions.md` §5.2's "`agent_os_kernel` (or equivalent)" naming note.
    return "nova_agent_os_" + name.replace("-", "_")


def _title(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("-"))


def _env_prefix(name: str) -> str:
    return ("agent_os_" + name).upper().replace("-", "_")


def _render(component_dir: Path, module: str, name: str, title: str, env_prefix: str) -> None:
    src = component_dir / "src" / module
    (src / "domain").mkdir(parents=True)
    (src / "events").mkdir(parents=True)
    (src / "repository").mkdir(parents=True)
    (component_dir / "tests" / "unit").mkdir(parents=True)
    (component_dir / "tests" / "integration").mkdir(parents=True)
    (component_dir / "tests" / "fakes").mkdir(parents=True)

    (component_dir / "pyproject.toml").write_text(
        _PYPROJECT_TOML.format(name=name, module=module)
    )
    (component_dir / "package.json").write_text(_PACKAGE_JSON.format(name=name, module=module))
    (component_dir / "README.md").write_text(
        _README.format(name=name, title=title, module=module)
    )

    (src / "__init__.py").write_text(_INIT_PY.format(title=title))
    (src / "py.typed").write_text("")
    (src / "config.py").write_text(_CONFIG_PY.format(env_prefix=env_prefix, title=title))
    (src / "main.py").write_text(_MAIN_PY.format(module=module, name=name))

    (src / "domain" / "__init__.py").write_text(_DOMAIN_INIT_PY.format(title=title))
    (src / "events" / "__init__.py").write_text(_EVENTS_INIT_PY)
    (src / "events" / "published.py").write_text(_PUBLISHED_PY.format(title=title))
    (src / "events" / "subscribed.py").write_text(_SUBSCRIBED_PY.format(title=title))
    (src / "repository" / "__init__.py").write_text(_REPOSITORY_INIT_PY.format(title=title))

    (component_dir / "tests" / "__init__.py").write_text("")
    (component_dir / "tests" / "unit" / "__init__.py").write_text("")
    (component_dir / "tests" / "integration" / "__init__.py").write_text("")
    (component_dir / "tests" / "fakes" / "__init__.py").write_text("")
    (component_dir / "tests" / "integration" / "test_health.py").write_text(
        _TEST_HEALTH_PY.format(module=module)
    )


# Same four contracts `tools/scaffold-engine.py` auto-populates, for the same
# reason: an agent-os component is bound by the identical ADR-004/006/007/034
# boundary rules an engine is (independent, no direct broker/graph-db client,
# no engine-specific knowledge leaking into nova-service-kit). Deliberately
# excludes the ADR-020 "no LLM SDK" and nova-testkit contracts, matching
# scaffold-engine.py's own documented, unrelated judgment call.
_CONTRACT_MODULES_KEY = {
    "Engines are independent (ADR-004): no engine imports another "
    "engine's internals directly": "modules",
    "No engine imports a message broker client directly (ADR-006): "
    "only nova_eventbus_sdk may": "source_modules",
    "No engine imports a graph database client directly (ADR-007): "
    "only nova_graphstore_sdk may": "source_modules",
    "nova-service-kit has no engine-specific knowledge (ADR-034): it "
    "may not import any engine's own top-level package": "forbidden_modules",
}


def _register_uv_workspace_glob(doc: tomlkit.TOMLDocument) -> None:
    members = doc["tool"]["uv"]["workspace"]["members"]
    if _WORKSPACE_GLOB not in members:
        members.append(_WORKSPACE_GLOB)


def _register_pnpm_workspace_glob() -> None:
    text = PNPM_WORKSPACE.read_text()
    entry_line = f'  - "{_WORKSPACE_GLOB}"'
    if entry_line in text.splitlines():
        return
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "packages:":
            lines.insert(i + 1, entry_line + "\n")
            break
    else:
        raise SystemExit(f"{PNPM_WORKSPACE} has no top-level 'packages:' key.")
    PNPM_WORKSPACE.write_text("".join(lines))


def _update_root_pyproject(module: str) -> None:
    """Generalizes `scaffold-engine.py`'s `_update_root_pyproject` (TDD 3E
    §3's explicit requirement) for `agent-os/`: in addition to import-linter
    registration, ensures `[tool.uv.workspace].members` actually globs
    `agent-os/*` -- unlike `services/*`, which every engine has always found
    already present, `agent-os/*` does not yet exist in either workspace
    manifest (`01-tdd-preparation-and-fork-resolutions.md` §5.2), so the
    first agent-os component to be scaffolded must add it.
    """
    doc = tomlkit.parse(ROOT_PYPROJECT.read_text())
    _register_uv_workspace_glob(doc)

    importlinter = doc["tool"]["importlinter"]
    root_packages = importlinter["root_packages"]
    if module not in root_packages:
        root_packages.append(module)

    for contract in importlinter["contracts"]:
        key = _CONTRACT_MODULES_KEY.get(contract.get("name"))
        if key is None:
            continue
        modules = contract[key]
        if module not in modules:
            modules.append(module)

    ROOT_PYPROJECT.write_text(tomlkit.dumps(doc))
    _register_pnpm_workspace_glob()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="kebab-case name, e.g. kernel, registry, supervisors")
    args = parser.parse_args()

    _validate_name(args.name)
    module = _module_name(args.name)
    title = _title(args.name)
    env_prefix = _env_prefix(args.name)
    component_dir = AGENT_OS_DIR / args.name

    _render(component_dir, module, args.name, title, env_prefix)
    _update_root_pyproject(module)

    print(f"Created agent-os/{args.name} ({module}).")
    print("Next steps:")
    print("  1. uv sync --all-packages")
    print(f"  2. Fill in src/{module}/domain/, events/published.py, events/subscribed.py")
    print(f"  3. uv run --package {args.name} pytest agent-os/{args.name}/tests")
    print("  4. uv run lint-imports   # confirm the new component is covered")
    return 0


_PYPROJECT_TOML = '''[project]
name = "{name}"
version = "0.1.0"
description = "TODO: describe {name}'s responsibility (docs/architecture/12-agent-architecture.md)."
requires-python = ">=3.12"
dependencies = [
    "nova-contracts",
    "nova-eventbus-sdk",
    "nova-observability",
    "nova-service-kit",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{module}"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
nova-contracts = {{ workspace = true }}
nova-eventbus-sdk = {{ workspace = true }}
nova-observability = {{ workspace = true }}
nova-service-kit = {{ workspace = true }}
nova-testkit = {{ workspace = true }}

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "nova-testkit",
]
'''

_PACKAGE_JSON = """{{
  "name": "@nova/{name}",
  "private": true,
  "version": "0.1.0",
  "scripts": {{
    "lint": "uv run --package {name} ruff check . && uv run --package {name} mypy src",
    "test": "uv run --package {name} pytest",
    "build": "echo '{name}: no build step (container image build deferred until deployment)'",
    "dev": "uv run --package {name} uvicorn {module}.main:app --reload --port 8000"
  }}
}}
"""

_README = """# agent-os/{name}

TODO: one paragraph describing this NAOS component's responsibility
(docs/architecture/12-agent-architecture.md).

Not an instance of the standard `-engine` template
(docs/architecture/02-repository-and-folder-structure.md:53-65) -- no
`/v1/...` REST surface; `/internal/health`/`/internal/readiness` come from
`nova-service-kit`'s `make_health_router()` (unmodified reuse), `/internal/
metrics` from `nova-observability`'s `prometheus_asgi_app()`.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| TODO | TODO | TODO |

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

## Testing

```bash
uv run --package {name} pytest agent-os/{name}/tests
```
"""

_INIT_PY = '''"""{title}. TODO: one paragraph on responsibility
(docs/architecture/12-agent-architecture.md)."""
'''

_CONFIG_PY = '''"""{title} configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="{env_prefix}_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    postgres_dsn: str = "postgresql+asyncpg://nova:nova@localhost:5432/nova"
'''

_MAIN_PY = '''"""{module}'s FastAPI entrypoint -- health/readiness/metrics only (TDD 3E
§4: `agent-os/{name}` is control-plane infrastructure, not a `/v1/...`
request/reply service)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from {module}.config import Settings
from {module}.events.published import PUBLISHABLE_SUBJECTS
from {module}.events.subscribed import SUBSCRIBABLE_SUBJECTS

logger = get_logger("{name}")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_observability("{name}", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="{name}",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("{name} starting")
        await bus.connect()
        app.state.bus = bus
        app.state.ready = True
        yield
        logger.info("{name} shutting down")
        app.state.ready = False
        await bus.close()

    fastapi_app = FastAPI(title="{name}", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()
'''

_DOMAIN_INIT_PY = '''"""{title}'s domain logic.

Framework-free by design (docs/architecture/03-backend-architecture.md §1): this
package must never import FastAPI, SQLAlchemy, or the Event Bus SDK directly. It
depends on ports defined here; `events/` and `repository/` implement them.
"""
'''

_EVENTS_INIT_PY = '''"""This component's declared Event Bus surface -- checked against
`nova-contracts` in CI (docs/architecture/16-testing-strategy.md §4) and enforced
at runtime by `BoundEventBus` (docs/architecture/09-event-bus-architecture.md §6)."""
'''

_PUBLISHED_PY = '''"""Every subject {title} is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md)."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {{
        # TODO: e.g. "agent_os.instance.inbox",
    }}
)
'''

_SUBSCRIBED_PY = '''"""Every subject {title} is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {{
        # TODO: e.g. "planning.task_graph.created",
    }}
)
'''

_REPOSITORY_INIT_PY = '''"""Data access layer for {title} -- never imported outside this component
(docs/architecture/03-backend-architecture.md §1)."""
'''

_TEST_HEALTH_PY = '''from fastapi.testclient import TestClient
from {module}.config import Settings
from {module}.main import create_app


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings())
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
'''


if __name__ == "__main__":
    sys.exit(main())
