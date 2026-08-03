# 18 — Local-First Architecture with Optional Cloud Synchronization

## 1. Principle

Part 7: "Whenever feasible, NOVA should prioritize local execution... cloud models
become optional enhancements, not mandatory components." Part 16: "sensitive
information should remain local whenever possible... cloud storage remains optional."
This is not a deployment detail — it is a product commitment that shapes the data
architecture from the start, not something bolted on after a cloud-first design.

## 2. What "local-first" means concretely

- The full cognitive loop (Perception → World Model → Memory/Knowledge → Reasoning →
  Planning → Action → Communication) runs with **every store on the user's own
  machine** ([07](07-database-architecture.md)) and **every model call served locally**
  via Ollama ([06](06-ai-layer-architecture.md)).
- No engine has a hard runtime dependency on internet connectivity. Cloud-dependent
  features (cloud model routing, multi-device sync, backups to a remote bucket) detect
  their own unavailability and degrade per Part 7's "Offline Mode": "internet dependent
  features should deactivate gracefully."
- The user owns their data outright: every store is a standard, inspectable format
  (Postgres, Neo4j, files) on their own disk — not a proprietary format requiring NOVA
  to be running to be readable, and exportable per Part 16's "User Control" ("export
  profile," "export twin").

## 3. Sync architecture (opt-in)

When a user enables multi-device or cloud backup, NOVA does **not** switch to a
cloud-primary model — it adds a synchronization layer on top of the still-authoritative
local stores:

```mermaid
flowchart LR
    subgraph Device A (primary)
    PGA[(Local Postgres)]
    NeoA[(Local Neo4j)]
    end
    subgraph Device B (laptop)
    PGB[(Local Postgres)]
    NeoB[(Local Neo4j)]
    end
    subgraph Cloud (optional)
    SyncSvc[nova-sync-service]
    ObjS[(S3 - encrypted blobs)]
    end
    PGA <-- CRDT/event log --> SyncSvc
    PGB <-- CRDT/event log --> SyncSvc
    SyncSvc --- ObjS
```

- **Sync unit:** the same Event Bus envelope used internally ([09](09-event-bus-architecture.md))
  is the sync payload — every durable state change already exists as a JetStream event
  with `event_id`/`causation_id`, so sync is "replay this device's event log to the
  cloud mirror and pull down others," not a bespoke second serialization format.
- **Conflict resolution:** last-writer-wins per field is insufficient for cognitive
  state, so sync uses the same confidence/recency/policy resolution the World Model
  already implements for conflicting observations ([10 §4](10-inter-engine-communication.md#4-consistency-model)) —
  one conflict-resolution algorithm, reused, rather than a second one invented for sync.
- **Encryption:** all data leaving the device is encrypted client-side with a
  user-held key before it touches `nova-sync-service` or S3 — the cloud component
  never has plaintext access, satisfying Part 16 "Privacy First" even in sync mode.
- **Granularity:** sync is opt-in **per domain** (Part 16 "Disable domains"): a user
  can sync Projects and Preferences across devices while keeping Episodic Memory
  device-local, for example.

## 4. What runs in the cloud, optionally

| Component | Local-first default | Optional cloud upgrade |
|---|---|---|
| Model inference | Ollama, local models | Cloud model connectors (Anthropic/OpenAI/Google/...) |
| Storage | Postgres/Neo4j/Redis/MinIO on-device | Managed Postgres/Neo4j + S3, via `nova-sync-service` |
| Compute for background cognition | Local CPU/GPU, scheduled during idle | Optional burst compute for heavy consolidation/indexing jobs |
| Multi-device presence | N/A (single device) | `nova-sync-service` + presence in `ws-gateway` |

## 5. Enterprise as a superset, not a fork

Enterprise/cloud deployment ([14](14-deployment-architecture.md),
[19](19-scalability-strategy.md)) is this same sync architecture generalized: instead
of "my devices," the cloud tenant *is* the primary store for an organization's shared
projects, and individual users' local-first installs (if used) sync against it the same
way Device B syncs against Device A above. No separate enterprise data model was
designed — the local-first architecture already had to solve "more than one
authoritative-feeling copy of the truth," and enterprise multi-user is the same problem
at a different topology.

## 6. Zero-budget guarantee

A fresh `git clone` + `docker compose up` with no API keys, no cloud account, and no
payment method produces a fully functional NOVA (Part 7 "Initial Zero Budget
Strategy"). This is a tested invariant, not an aspiration: the E2E "golden path" test
in [16 §6](16-testing-strategy.md) runs against exactly this configuration in CI, so a
future change that accidentally introduces a hard cloud dependency fails the build.
