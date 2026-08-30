# NOVA Project Bible

NOVA — **N**eural **O**perational **V**irtual **A**rchitecture — is the specification
for an Artificial Intelligence Operating System: a cognitive platform composed of an
AI Core, a multi-layer Memory Engine, a Multi-Agent Intelligence System, a World Model,
and a set of specialized engines (Reasoning, Planning, Knowledge, Perception, Action,
Communication, Autonomy, Capability, Digital Twin, Personality, Executive Cognition) that
together are meant to present a single, consistent intelligence to the user.

This repository is the authoritative source of truth for that architecture, and is now
also where NOVA is actually being built, phase by phase, against that specification.

## Contents

The full specification is split by section under [`docs/bible`](docs/bible/README.md):

- [System Instruction](docs/bible/00-system-instruction.md) — the architectural mandate
  and how the rest of the document is to be treated.
- Twenty parts, one engine or subsystem per part, from foundational vision and product
  philosophy through the AI Core, Memory Engine, Multi-Agent System, World Model,
  Cognitive State Engine, and on to NOVA Core.

See [`docs/bible/README.md`](docs/bible/README.md) for the full table of contents.

In addition to the Bible, this repository contains the **Software Architecture
Document (SAD)** and **Engineering Roadmap** that translate the Bible into a concrete,
production engineering plan:

- [`docs/architecture`](docs/architecture/README.md) — technology stack, repository
  structure, and per-subsystem architecture (backend, frontend, desktop, AI layer,
  databases, memory, event bus, inter-engine communication, APIs, agents, security,
  deployment, workflow, testing, CI/CD, local-first/cloud sync, and scalability).
- [`docs/roadmap/ENGINEERING_ROADMAP.md`](docs/roadmap/ENGINEERING_ROADMAP.md) — the
  phased implementation plan (objectives, deliverables, dependencies, complexity,
  order, testing strategy, and acceptance criteria per phase).

## Implementation

The monorepo scaffold described in
[`docs/architecture/02`](docs/architecture/02-repository-and-folder-structure.md) lives
at the repository root: `packages/` (shared libraries, including the `EventBus` and
schema contracts from ADR-006), `services/` (engines — `nova-core` so far), `tools/`
(`scaffold-engine.py`, the import-boundary linter config), and `infra/` (the local-first
Docker Compose stack + observability configuration).

```bash
pnpm install && uv sync --all-packages   # bootstrap
pnpm turbo run lint test                 # lint + test every package
uv run lint-imports                      # verify ADR-004 / ADR-006 boundaries
docker compose -f infra/docker/docker-compose.local.yml up -d   # full local stack
```


## Status

**Phases 0 through 3D are implemented and merged. Phase 3E
(`agent-os` + the five Agent Packages + the `engineering` Supervisor) is
implemented on branch `phase-3e-agent-os` (last production-source commit
`60934ac`) but is not
merged, has no open PR, and has had no GitHub Actions run — its Gate
Review verdict is CONDITIONAL-GO, not Go.** `nova-core` boots through its
full 7-phase sequence, exposes `/internal/health`, `/internal/readiness`, and
`/internal/metrics`, and publishes its heartbeat over the Event Bus — see
[`docs/roadmap/ENGINEERING_ROADMAP.md`](docs/roadmap/ENGINEERING_ROADMAP.md#phase-0--platform-bootstrap)
for Phase 0's full acceptance criteria. Thirteen engines are implemented on the
canonical `phase-3b-planning-domain` branch (Memory, Knowledge, World Model, AI Model
Orchestration, Reasoning, Executive Cognition, Communication, Personality,
Perception, Digital Twin, Planning, Capability, Action); `action-engine`
(Phase 3D) merged 2026-08-18 via PR #13 (squash commit
`ac285bc3533fb24d0434d7675b8fc3af2db1d079`). Phase 3E adds, on its own
unmerged branch, four `agent-os` components (`kernel`, `registry`,
`supervisors`, `sdk/python`) and five Agent Packages under `agents/`
(`research`, `coding`, `qa`, `architect`, `documentation`) — neither
directory is an engine, and `agent-os/*` has no Dockerfile and is not yet
in the `build-and-scan.yml` matrix or `docker-compose.local.yml`. See
[`docs/project-health/project-health-master.md`](docs/project-health/project-health-master.md)
for the full, per-phase longitudinal status record (tests, coverage, CI, real-infra,
and documentation health for every completed phase) and each phase's own Gate
Review under [`docs/roadmap/architecture-reviews/`](docs/roadmap/architecture-reviews/)
for full detail.
