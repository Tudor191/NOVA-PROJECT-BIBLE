#!/usr/bin/env python3
"""Generate a new `agents/<name>-agent` Agent Package (doc 12 §3's exact
`agent.yaml` + `src/handler.py` + `tests/` layout, `12-agent-architecture.md
:53-59`) -- structurally nothing like either the engine template or the
agent-os component template (Fork 3E-4, resolved: docs/design/phase-3/
08-tdd-3e-agent-os.md §3, §11).

Usage:
    uv run python tools/scaffold-agent-package.py <name>-agent   # e.g. research-agent

Deliberately generates NO `pyproject.toml` / `package.json` and registers
nothing in `[tool.uv.workspace].members`, `pnpm-workspace.yaml`, or
import-linter -- an Agent Package is not a uv/pnpm workspace member. Doc 12
§6/§15 is explicit that Phase 3's Agent Registry discovery is
"filesystem-based (agents declared in the monorepo)": the install pipeline
reads `agent.yaml` and loads `src/handler.py` directly off disk (a
package-manager/plugin model, not a build-time Python distribution) --
confirmed by `01-tdd-preparation-and-fork-resolutions.md` §5.2's own
concrete-config-changes table, which lists `agent-os/*` as a needed
workspace-glob addition but never mentions `agents/*` for the same
treatment.

`src/handler.py`'s generated stub imports `nova_agent_sdk` (`agent-os/sdk/
python`'s `AgentHandler` Protocol, doc 12 §4) by its documented, intended
import path -- that package is a separate, not-yet-built TDD 3E deliverable
(§0's own build order puts the SDK after Kernel/Registry), so the generated
stub will not actually import successfully until it exists. This is
disclosed, not silently papered over: the generated smoke test validates
`agent.yaml`'s presence and required keys only (self-contained, runnable
today), not `handler.py`'s own SDK-dependent import.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-agent$")


def _validate_name(name: str) -> None:
    if not _NAME_PATTERN.match(name):
        raise SystemExit(
            f"Invalid agent package name {name!r}. Expected kebab-case ending in "
            f"'-agent', e.g. 'research-agent'."
        )
    if (AGENTS_DIR / name).exists():
        raise SystemExit(f"agents/{name} already exists.")


def _title(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("-"))


def _render(agent_dir: Path, name: str, title: str) -> None:
    (agent_dir / "src").mkdir(parents=True)
    (agent_dir / "tests").mkdir(parents=True)

    (agent_dir / "agent.yaml").write_text(_AGENT_YAML.format(name=name, title=title))
    (agent_dir / "src" / "handler.py").write_text(_HANDLER_PY.format(title=title))
    (agent_dir / "README.md").write_text(_README.format(name=name, title=title))
    (agent_dir / "tests" / "test_agent_package.py").write_text(
        _TEST_AGENT_PACKAGE_PY.format(name=name)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="kebab-case name ending in '-agent', e.g. research-agent")
    args = parser.parse_args()

    _validate_name(args.name)
    title = _title(args.name)
    agent_dir = AGENTS_DIR / args.name

    _render(agent_dir, args.name, title)

    print(f"Created agents/{args.name}.")
    print("Next steps:")
    print(f"  1. Fill in agents/{args.name}/agent.yaml (category, capabilities, permissions)")
    print(f"  2. Implement agents/{args.name}/src/handler.py against agent-os/sdk/python's")
    print("     AgentHandler Protocol once that SDK exists")
    print(f"  3. uv run pytest agents/{args.name}/tests")
    return 0


_AGENT_YAML = '''# agent.yaml -- the Agent Package manifest
# (docs/architecture/12-agent-architecture.md §3)
id: {name}
version: 0.1.0
category: TODO                      # Part 4 taxonomy: research, architect, backend,
                                     # frontend, ai-engineering, ml, coding, devops,
                                     # database, cybersecurity, vision, voice, browser,
                                     # desktop-control, knowledge, memory, automation,
                                     # calendar, communication, gaming, finance, health,
                                     # education, creative, product-manager, qa, ...
display_name: "{title}"
required_capabilities: []           # resolved by capability-engine at execution time
required_permissions: []            # declared-intent-only in Phase 3 (TDD 3E §5/§8a item 5,
                                     # no nova-auth -- see this package's README)
supported_execution_backends:
  - inprocess                        # Phase 3 ships inprocess only (TDD 3E §2)
resource_profile:
  cpu: standard
  memory: standard
  gpu: none
health_check:
  interval_seconds: 30
compatibility:
  min_kernel_version: "0.1.0"
'''

_HANDLER_PY = '''"""{title} -- implements the Agent SDK's `AgentHandler` Protocol
(docs/architecture/12-agent-architecture.md §4).

TODO: this stub imports `nova_agent_sdk`, which does not exist yet
(`agent-os/sdk/python` is a separate, not-yet-built TDD 3E deliverable) --
this file will not import successfully until that package ships. Left as
the documented, intended shape rather than invented differently, per
`docs/design/phase-3/08-tdd-3e-agent-os.md` §3/§11.

`on_assign`'s `task` parameter is typed `TaskNodeSnapshot` (`nova_contracts`),
not planning-engine's own domain `TaskNode` doc 12 §4 names -- the same
domain-vs-wire-payload split already applied to `AgentContext.task`
(`nova_contracts.entities`, Phase 3E Milestone 1): a cross-engine consumer
gets the published wire snapshot, never another engine's internal domain
type (ADR-004).
"""

from __future__ import annotations

from nova_agent_sdk import (
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMessage,
    AgentMetrics,
    AgentResult,
    ValidationOutcome,
)
from nova_contracts import TaskNodeSnapshot


class Handler(AgentHandler):
    async def on_load(self, manifest: AgentManifest) -> None:
        raise NotImplementedError

    async def on_unload(self) -> None:
        raise NotImplementedError

    async def on_assign(self, task: TaskNodeSnapshot, context: AgentContext) -> None:
        raise NotImplementedError

    async def execute(self) -> AgentResult:
        raise NotImplementedError

    async def on_pause(self) -> None:
        raise NotImplementedError

    async def on_resume(self) -> None:
        raise NotImplementedError

    async def self_validate(self, result: AgentResult) -> ValidationOutcome:
        raise NotImplementedError

    async def health_check(self) -> AgentHealth:
        raise NotImplementedError

    async def on_message(self, message: AgentMessage) -> AgentMessage | None:
        raise NotImplementedError

    def metrics_snapshot(self) -> AgentMetrics:
        raise NotImplementedError
'''

_README = """# agents/{name}

TODO: one paragraph describing {title}'s responsibility (Bible Part 4).

Not a uv/pnpm workspace member -- the Agent Registry's Phase 3 discovery is
filesystem-based (docs/architecture/12-agent-architecture.md §6, §15): it
reads `agent.yaml` and loads `src/handler.py` directly off disk.

**Not yet runnable.** `src/handler.py` implements `agent-os/sdk/python`'s
`AgentHandler` Protocol, which does not exist yet -- this package cannot be
loaded by the Kernel/Registry until that SDK ships.

## Testing

```bash
uv run pytest agents/{name}/tests
```
"""

_TEST_AGENT_PACKAGE_PY = '''"""Structural smoke test for the {name} Agent Package.

Deliberately does not import `src/handler.py` -- it depends on `agent-os/
sdk/python`'s `AgentHandler` Protocol (doc 12 §4), a separate, not-yet-built
TDD 3E deliverable (see this package's own README). Once the SDK exists and
this package is wired into the Agent Registry's install pipeline (doc 12
§6), replace this with a real `on_load`/`execute`/`health_check` test.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def test_agent_yaml_exists_and_declares_required_top_level_keys() -> None:
    manifest_text = (PACKAGE_DIR / "agent.yaml").read_text()
    for key in (
        "id:",
        "version:",
        "category:",
        "required_capabilities:",
        "required_permissions:",
        "supported_execution_backends:",
    ):
        assert key in manifest_text, f"agent.yaml is missing required key {{key!r}}"


def test_handler_py_exists() -> None:
    assert (PACKAGE_DIR / "src" / "handler.py").is_file()
'''


if __name__ == "__main__":
    sys.exit(main())
