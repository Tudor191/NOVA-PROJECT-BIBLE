#!/usr/bin/env python3
"""Generate a new, CI-compliant engine under `services/` from the standard template
(docs/architecture/02-repository-and-folder-structure.md §3).

Usage:
    uv run python tools/scaffold-engine.py <name>       # e.g. memory-engine

The generated engine boots (FastAPI + lifespan-managed EventBus connection),
exposes `/internal/health`, `/internal/readiness`, `/internal/metrics`, declares
empty publish/subscribe allow-lists ready for its author to fill in, and ships with
one passing smoke test -- it passes `turbo run lint test` unmodified, exactly like
every hand-built engine, because it *is* the same template.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import tomlkit

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = REPO_ROOT / "services"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"

# `-gateway` is accepted alongside `-engine` (Phase 4 decision D-2). `api-gateway`
# and `ws-gateway` live under `services/` per doc 02 and are ordinary FastAPI
# services -- they are simply not domain "engines", so the generated skeleton
# (FastAPI app, health endpoints, Dockerfile) is exactly what they need. This gap
# was identified in `docs/design/phase-3/03-gateway-web-prerequisite.md` §2 and
# left unactioned there; without it neither gateway could be scaffolded at all.
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-(engine|gateway)$")


def _validate_name(name: str) -> None:
    if not _NAME_PATTERN.match(name):
        raise SystemExit(
            f"Invalid service name {name!r}. Expected kebab-case ending in "
            f"'-engine' or '-gateway', e.g. 'memory-engine' or 'api-gateway'."
        )
    if (SERVICES_DIR / name).exists():
        raise SystemExit(f"services/{name} already exists.")


def _module_name(name: str) -> str:
    return "nova_" + name.replace("-", "_")


def _title(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("-"))


def _env_prefix(name: str) -> str:
    return name.upper().replace("-", "_")


def _render(engine_dir: Path, module: str, name: str, title: str, env_prefix: str) -> None:
    src = engine_dir / "src" / module
    (src / "api").mkdir(parents=True)
    (src / "domain").mkdir(parents=True)
    (src / "events").mkdir(parents=True)
    (src / "models").mkdir(parents=True)
    (src / "repository").mkdir(parents=True)
    (engine_dir / "tests" / "unit").mkdir(parents=True)
    (engine_dir / "tests" / "integration").mkdir(parents=True)
    (engine_dir / "tests" / "contract").mkdir(parents=True)

    (engine_dir / "pyproject.toml").write_text(_PYPROJECT_TOML.format(name=name, module=module))
    (engine_dir / "package.json").write_text(_PACKAGE_JSON.format(name=name, module=module))
    (engine_dir / "Dockerfile").write_text(_DOCKERFILE.format(name=name, module=module))
    (engine_dir / "README.md").write_text(_README.format(name=name, title=title, module=module))

    (src / "__init__.py").write_text(_INIT_PY.format(title=title))
    (src / "py.typed").write_text("")
    (src / "config.py").write_text(_CONFIG_PY.format(env_prefix=env_prefix, title=title))
    (src / "main.py").write_text(_MAIN_PY.format(module=module, name=name))

    (src / "api" / "__init__.py").write_text(_API_INIT_PY)
    (src / "api" / "health.py").write_text(_HEALTH_PY)

    (src / "domain" / "__init__.py").write_text(_DOMAIN_INIT_PY.format(title=title))
    (src / "events" / "__init__.py").write_text(_EVENTS_INIT_PY)
    (src / "events" / "published.py").write_text(_PUBLISHED_PY.format(title=title))
    (src / "events" / "subscribed.py").write_text(_SUBSCRIBED_PY.format(title=title))
    (src / "models" / "__init__.py").write_text(_MODELS_INIT_PY.format(title=title))
    (src / "repository" / "__init__.py").write_text(_REPOSITORY_INIT_PY.format(title=title))

    (engine_dir / "tests" / "unit" / "__init__.py").write_text("")
    (engine_dir / "tests" / "integration" / "__init__.py").write_text("")
    (engine_dir / "tests" / "contract" / "__init__.py").write_text("")
    (engine_dir / "tests" / "integration" / "test_health.py").write_text(
        _TEST_HEALTH_PY.format(module=module)
    )


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
"""Deliberately excludes ADR-033's "nova-testkit has no engine-specific
knowledge" contract, matching this dict's pre-existing scope (the ADR-020 "no
LLM SDK" contract is excluded for a different, judgment-call reason -- see the
docstring below). That contract's own `forbidden_modules` list not being
auto-populated per new engine is a pre-existing gap, not introduced or widened
here; fixing it is unrelated to ADR-034 or the nova-service-kit extraction
this dict entry supports and is left for separate consideration."""
"""The 3 contracts (beyond `root_packages` itself) every new engine belongs in
by default. Deliberately excludes the ADR-020 "no LLM SDK" contract, which
`ai-model-orchestration-engine` itself must NOT appear in (it's the one engine
allowed to import an LLM SDK) -- that contract has always required a manual,
judgment-call edit and still does; automating it is a separate decision, not
part of this fix."""


def _update_root_pyproject(module: str) -> None:
    """Add the new engine to the workspace-wide import-boundary contracts
    (docs/architecture/00-overview-and-decisions.md, ADR-004) so it's enforced from
    its very first commit, exactly like every other engine.

    Uses `tomlkit` (parses and re-serializes losslessly, preserving comments and
    formatting) rather than literal-string matching. The original implementation
    matched a literal `root_packages = [\\n    "nova_core",\\n]` pattern that only
    existed while `nova_core` was the *only* entry in each list -- true for the
    very first engine scaffolded after `nova-core`, false for every one after
    that, so `str.replace()` silently returned the text unchanged from the third
    engine onward, with no error and no warning (Project Health Review, August
    2026 -- confirmed by testing the same pattern against the current file, which
    already has 9 engines listed: zero matches). Every engine from
    `knowledge-engine` on had to be added to these contracts by hand as a result.
    """
    doc = tomlkit.parse(ROOT_PYPROJECT.read_text())
    importlinter = doc["tool"]["importlinter"]

    root_packages = importlinter["root_packages"]
    if module in root_packages:
        return
    root_packages.append(module)

    for contract in importlinter["contracts"]:
        key = _CONTRACT_MODULES_KEY.get(contract.get("name"))
        if key is None:
            continue
        modules = contract[key]
        if module not in modules:
            modules.append(module)

    ROOT_PYPROJECT.write_text(tomlkit.dumps(doc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="kebab-case name ending in '-engine', e.g. memory-engine")
    args = parser.parse_args()

    _validate_name(args.name)
    module = _module_name(args.name)
    title = _title(args.name)
    env_prefix = _env_prefix(args.name)
    engine_dir = SERVICES_DIR / args.name

    _render(engine_dir, module, args.name, title, env_prefix)
    _update_root_pyproject(module)

    print(f"Created services/{args.name} ({module}).")
    print("Next steps:")
    print("  1. uv sync --all-packages")
    print(f"  2. Fill in src/{module}/domain/, events/published.py, events/subscribed.py")
    print(f"  3. uv run --package {args.name} pytest services/{args.name}/tests")
    print("  4. uv run lint-imports   # confirm the new engine is covered")
    return 0


_PYPROJECT_TOML = '''[project]
name = "{name}"
version = "0.1.0"
description = "TODO: describe {name}'s responsibility (one Bible Part -- see docs/architecture/00)."
requires-python = ">=3.12"
dependencies = [
    "nova-contracts",
    "nova-eventbus-sdk",
    "nova-observability",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic-settings>=2.6",
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
    "build": "echo '{name}: no build step (container image built via Dockerfile in CI)'",
    "dev": "uv run --package {name} uvicorn {module}.main:app --reload --port 8000"
  }}
}}
"""

_DOCKERFILE = """# Build context is the repo root (docker build -f services/{name}/Dockerfile .).
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/nova-contracts/pyproject.toml packages/nova-contracts/pyproject.toml
COPY packages/nova-eventbus-sdk/pyproject.toml packages/nova-eventbus-sdk/pyproject.toml
COPY packages/nova-observability/pyproject.toml packages/nova-observability/pyproject.toml
COPY services/{name}/pyproject.toml services/{name}/pyproject.toml

COPY packages/nova-contracts packages/nova-contracts
COPY packages/nova-eventbus-sdk packages/nova-eventbus-sdk
COPY packages/nova-observability packages/nova-observability
COPY services/{name} services/{name}

RUN uv sync --frozen --no-dev --package {name}

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 nova
WORKDIR /app
COPY --from=builder --chown=nova:nova /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nova

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \\
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/internal/health')"

CMD ["uvicorn", "{module}.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

_README = """# {name}

TODO: one paragraph describing this engine's responsibility, and which Bible Part
(docs/bible/) it implements.

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
uv run --package {name} pytest services/{name}/tests
```
"""

_INIT_PY = '''"""{title}. TODO: one paragraph on responsibility and the Bible Part it implements."""
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
'''

_MAIN_PY = '''"""{module}'s FastAPI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from {module}.api.health import router as health_router
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
    fastapi_app.include_router(health_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()
'''

_API_INIT_PY = '''"""HTTP route handlers -- thin, delegating to `domain/`
(docs/architecture/03 §1)."""
'''

_HEALTH_PY = '''"""`/internal/health` and `/internal/readiness`
(docs/architecture/11-api-architecture.md §3)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    ready: bool


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get("/readiness")
async def readiness(request: Request) -> ReadinessResponse:
    return ReadinessResponse(ready=bool(getattr(request.app.state, "ready", False)))
'''

_DOMAIN_INIT_PY = '''"""{title}'s domain logic -- the actual engine intelligence.

Framework-free by design (docs/architecture/03-backend-architecture.md §1): this
package must never import FastAPI, SQLAlchemy, or the Event Bus SDK directly. It
depends on ports defined here; `api/`, `events/`, and `repository/` implement them.
"""
'''

_EVENTS_INIT_PY = '''"""This engine's declared Event Bus surface -- checked against
`nova-contracts` in CI (docs/architecture/16-testing-strategy.md §4) and enforced
at runtime by `BoundEventBus` (docs/architecture/09-event-bus-architecture.md §6)."""
'''

_PUBLISHED_PY = '''"""Every subject {title} is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md)."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {{
        # TODO: e.g. "your_engine.entity.created",
    }}
)
'''

_SUBSCRIBED_PY = '''"""Every subject {title} is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {{
        # TODO: e.g. "perception.*.observed",
    }}
)
'''

_MODELS_INIT_PY = '''"""SQLAlchemy / Neo4j / Pydantic models owned by {title}."""
'''

_REPOSITORY_INIT_PY = '''"""Data access layer for {title} -- never imported outside this engine
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
