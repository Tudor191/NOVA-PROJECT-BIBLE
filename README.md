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

**Phase 0 (Platform Bootstrap) implemented and passing CI locally.** `nova-core` boots
through its full 7-phase sequence, exposes `/internal/health`, `/internal/readiness`,
and `/internal/metrics`, and publishes its heartbeat over the Event Bus — see
[`docs/roadmap/ENGINEERING_ROADMAP.md`](docs/roadmap/ENGINEERING_ROADMAP.md#phase-0--platform-bootstrap)
for the full acceptance criteria. Phases 1+ (Memory/Knowledge/World Model, the AI
Core, the NOVA Agent Operating System, and everything after) have not started.
