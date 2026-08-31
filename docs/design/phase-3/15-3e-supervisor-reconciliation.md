# 15 — Phase 3E Supervisor Milestone: Reconciliation of Two Disclosed Items

**Status: investigation complete. Item A was a genuine architectural
conflict, stopped and reported per explicit instruction, then resolved
2026-08-23 by explicit user decision (see §A's "Resolution" subsection)
and implemented. Item B is resolved as a documented conclusion; no
implementation change required.**

This document is the focused reconciliation the user's Supervisor-milestone
instruction required before Agent Package work may begin. It does not
propose new architecture and does not reopen any of the six approved Phase
3E decisions on its own authority.

---

## A. Registry idempotency key — `(id, version)` vs `(category, version)`

### The conflict, precisely

Two independent sources disagree, and both sides carry real weight:

**Side 1 — doc 12 (`docs/architecture/12-agent-architecture.md`) says `(id, version)`:**
- §3's `agent.yaml` worked example: `id: coding-agent`, `category: coding` —
  two distinct fields, `id` the package's own name, `category` a Part-4
  taxonomy classification.
- §6's own worked example: "The Registry can hold `coding-agent@1.2.0` and
  `coding-agent@1.3.0` simultaneously" — `coding-agent` is the manifest's
  own `id`, not its `category`. The mermaid flowchart's Register step lists
  three separate fields: "id, version, category, health=unknown."
- §15's table: versioning is "mechanism exists from Phase 3, exercised as
  soon as two versions of one agent actually need to coexist" — per-agent
  (per-`id`) multi-version coexistence, not per-category.

**Side 2 — TDD 3E §5's prose, and the *already-approved* Fork 3E-2 ORM, say `(category, version)`:**
- TDD 3E §5, literal text: "the Registry's persistence keys on
  `(category, version)`, not `category` alone."
- TDD 3E §4's own resolution note bundles `agent_package`'s exact schema
  into **Fork 3E-2** ("Kernel persistence schema"), already approved
  2026-08-19: *"Approved: the proposed `agent_os` Postgres schema,
  `agent_instance` + `agent_package` tables, adopted as-is... exact
  SQLAlchemy ORM given [in `14-3e-agent-os-research.md` §4]."*
- That research document's own concrete, approved ORM
  (`14-3e-agent-os-research.md` §4):
  ```python
  class AgentPackageORM(Base):
      __tablename__ = "agent_package"
      id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
      category: Mapped[str] = mapped_column(Text, nullable=False)
      version: Mapped[str] = mapped_column(Text, nullable=False)
      manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
      installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
      health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
      __table_args__ = (UniqueConstraint("category", "version"),)
  ```
  `id` here is a **surrogate UUID primary key** — not the manifest's own
  string `id` ("coding-agent"). There is no separate string field for the
  manifest's own package name anywhere in this approved shape. Uniqueness
  is a `UniqueConstraint("category", "version")`, matching TDD 3E §5's
  prose exactly.
- The research document's own rationale claims this "directly implements
  doc 12 §6's own multi-version-coexistence requirement... using the
  identical keying strategy `capability-engine`'s own install-idempotency
  (Fork 3C-4) already established for its own `(name, version)` pair" —
  but `capability-engine`'s actual `CapabilityORM`
  (`services/capability-engine/src/nova_capability_engine/repository/models.py`)
  has **both** `id` (UUID PK) **and** a separate `name: Mapped[str]` field
  (the capability's own identifier, e.g. `"git"`), with
  `UniqueConstraint("name", "version")` — `name` is the analogue of
  `agent.yaml`'s `id`, not of `category`. The approved `AgentPackageORM`
  does not carry this parallel: it substituted `category` where the
  `capability-engine` precedent it cites would call for a `name`/agent-id
  field. The research document's own stated rationale and its own code do
  not agree with each other.

**Corroborating evidence this is load-bearing, not academic:** Kernel's
own, already-built `AgentInstanceORM` (Milestone 2,
`agent-os/kernel/src/nova_agent_os_kernel/repository/models.py`) already
encodes the approved shape's assumption:
```python
agent_package_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
```
a UUID foreign-key-shaped column, consistent with `AgentPackageORM.id`
being a UUID surrogate key. Milestone 3's Registry implementation
(`agent-os/registry/src/nova_agent_os_registry/`), however, gives
`AgentPackage.id: str` (the manifest's own string id) as part of a
composite primary key `(id, version)` — no UUID surrogate key exists
anywhere in that schema. **Kernel and Registry currently assume two
different, incompatible shapes for the same conceptual identifier.** This
is not a paperwork inconsistency: it is a genuine schema mismatch between
two already-shipped components, discovered only by tracing the concrete
ORM the approved Fork 3E-2 resolution actually specifies.

### Why this is not resolved as an "additive documentation correction"

Milestone 3's own module docstrings (`domain/pipeline.py`,
`domain/models.py`, `repository/models.py`) already disclosed the
`(id, version)` choice as a probable wording correction against TDD 3E
§5's prose alone. That disclosure did not go far enough: it did not trace
the choice through to Fork 3E-2's own *already-approved* concrete ORM, or
to Kernel's own already-built `agent_package_id: UUID` column. Having
traced it now, `(id, version)` is not merely a fix for an isolated wording
slip — it is a deviation from a specific, concrete schema shape the user
already approved as part of one of the six Phase 3E decisions (Fork
3E-2). Changing implementation to match doc 12 (keep `(id, version)`) or
changing it back to match the approved ORM (`(category, version)` + a
UUID surrogate key) both touch that approved decision. Per this
milestone's explicit instruction — "If it represents a genuine
architectural decision, stop and report it before choosing a solution,"
and "Do not reopen the six approved Phase 3E architectural decisions" —
**this stops here.** No documentation or implementation change is made by
this pass.

### What is not in dispute

Both sides agree on the *purpose*: an `agent_package` row must be
addressable and support multiple coexisting versions per agent. They
disagree only on the *mechanism* (natural string key vs. surrogate UUID +
category-scoped uniqueness) and, as a direct consequence, on whether a
`category` can ever host two distinct agents (doc 12's taxonomy allows it
in principle; the approved ORM's literal uniqueness constraint would
silently forbid two same-category agents from ever sharing a version
number). Phase 3's own five shipped agents each have a distinct category,
so this divergence has no observable effect on Phase 3 itself — it would
only surface once a sixth agent is added sharing an existing category.

### Options for the user's decision (none chosen here)

1. **Amend Fork 3E-2's own record** to adopt `(id, version)` as a
   corrected shape (doc 12-aligned), and update Kernel's
   `agent_package_id` column type accordingly (`Text`, or a composite
   `(agent_package_id, agent_package_version)` pair) — a small, disclosed
   change to already-shipped Milestone 2 code.
2. **Revert Registry's schema** to the approved ORM exactly as specified
   (UUID surrogate PK, `UniqueConstraint("category", "version")`), and add
   the missing string field the `capability-engine` precedent implies
   (e.g. `agent_id: str`) so natural, doc-12-style `coding-agent@1.2.0`
   lookups remain possible without querying inside `manifest_json`.
3. Some other resolution the user prefers.

### Resolution (2026-08-23, per explicit user decision)

The user chose **option 2**: revert Registry's schema to the approved Fork
3E-2 ORM exactly as specified, *without* adding the extra string field
option 2's own text had speculated might be needed. The user's explicit
instruction gave the canonical shape as exactly two elements — a UUID
surrogate primary key, and `UniqueConstraint(category, version)` — and
named nothing else. Adding a third, unrequested field (e.g. an
`agent_id: str` column mirroring `capability-engine`'s `name`) would have
repeated the same failure mode that caused this conflict in the first
place: inventing architecture beyond what was actually approved. So the
manifest's own string `id` (e.g. `"coding-agent"`) remains recoverable
only from `manifest_json`, exactly as the approved ORM in
`14-3e-agent-os-research.md` §4 shows it — no separate column was added.
This is a scoping judgment made on this pass's own authority within the
user's explicit instruction, not a further-elaborated instruction from the
user; if the user wants a natural-key lookup column for the manifest's own
`id` (doc-12-style `coding-agent@1.2.0` addressing without querying inside
`manifest_json`), that remains open for a future, explicit decision.

**What was corrected, concretely:**

- `domain/models.py`: `AgentPackage.id` changed from `str` (the manifest's
  own id) to `UUID` (a surrogate key, mirroring Kernel's own
  `AgentInstance` treatment).
- `domain/ports.py`: `RegistryRepository.find_by_id_version` →
  `find_by_category_version`; `find_latest_by_id` →
  `find_latest_by_category`; `update_health_status` narrowed from
  `(package_id, version)` to `(package_id: UUID)` alone, since the
  surrogate key is now sufficient on its own.
- `repository/models.py` (`AgentPackageORM`): composite primary key
  `(id, version)` (`id: Text`) replaced with a single UUID primary key
  (`id: PG_UUID`) plus `UniqueConstraint("category", "version",
  name="uq_agent_package_category_version")` — now identical to the
  approved ORM in `14-3e-agent-os-research.md` §4.
- `repository/postgres_registry_repository.py`: all method bodies updated
  to match; the `(category, version)` unique-constraint violation is what
  now translates to `AgentPackageAlreadyExistsError`.
- `alembic/versions/0001_initial_schema.py`: `PRIMARY KEY (id, version)`
  (composite, `TEXT id`) replaced with `id UUID NOT NULL PRIMARY KEY` +
  `CONSTRAINT uq_agent_package_category_version UNIQUE (category,
  version)`; the now-redundant standalone `category` index was dropped
  (the composite unique index already serves category-only lookups via
  leftmost-prefix matching).
- `domain/pipeline.py`: Registration now mints `AgentPackage(id=uuid4(),
  ...)` in the domain layer (matching `capability-engine`'s own
  `Capability(id=uuid4(), ...)` convention) instead of using the
  manifest's own id as the primary key. The idempotency check
  (post-Manifest-Validation) and the race-condition re-check both key on
  `(category, version)`. The Permission Review stage's diff baseline
  changed from "the latest version of this same agent id" to "the latest
  install in this same category" — a direct, disclosed consequence of
  `(category, version)` keying (see "What is not in dispute" above); Phase
  3's five agents each have a distinct category, so this has no observable
  effect on Phase 3 itself.
- `tests/fakes/repository.py` and `tests/unit/test_pipeline.py`: updated
  to the corrected shape; two tests added — one proving two different
  categories may share a version, one proving a same-`(category,
  version)` reinstall is idempotent (returns the existing row) rather than
  a hard error.
- `tests/integration/test_repository_real_postgres.py`: updated to the
  corrected shape against a real Postgres schema (via this component's own
  Alembic migration), including a dedicated test that round-trips the
  surrogate UUID through insert → find → update to prove ORM/repository/
  migration consistency, and a real-Postgres-level test of the
  two-categories-share-a-version case.

**Not changed by this correction:** the eight-stage installation pipeline
(`InstallationStage` enum, unchanged); the Sandbox Test Run's structural
`AgentHandler`-conformance-only behavior (§B, below — untouched); no
`nova-auth` introduced anywhere; `checksum` and
`supervisor_notified_new_permissions` (Milestone-3-era bookkeeping,
unrelated to the idempotency-key shape) preserved as-is; no other approved
Phase 3E decision reopened.

---

## B. Registry Sandbox Test Run — structural conformance vs. behavioral isolation

### Conclusion

**Structural conformance only is the correct, intended scope for Phase 3.**
Milestone 3's implementation (`agent-os/registry/src/nova_agent_os_registry/domain/pipeline.py`'s
`SANDBOX_TEST` stage: dynamic `importlib` load of `handler.py` +
`issubclass(handler_class, AgentHandler)`) matches this conclusion exactly.
No implementation change is required.

### Evidence chain

- TDD 3E §5, literal text: *"'Sandbox test run' for an agent reuses Fork
  E3's lighter OS-level scoping discipline — no new isolation technology
  beyond what TDD 3C already established for capabilities."*
- TDD 3C §3 (`06-tdd-3c-capability-engine.md`), Fork E3's actual, approved
  mechanism table: path-prefix allow-lists (`filesystem`), executable
  allow-lists + `asyncio.create_subprocess_exec` (`terminal`), the same
  plus a repo-root scope (`git`), and outbound-host allow-lists (`http`).
  Every mechanism targets one of these four specific *capability adapter*
  resource types. None targets "arbitrary in-process Python code" — there
  is no fifth row for that, and TDD 3C §3 explicitly disclaims going
  further: closing the one gap it does name (a `terminal`/`git`
  subprocess's own outbound network calls) "would require process-level
  network isolation... a heavier isolation mechanism than the lighter
  OS-level scoping Fork E3 already approved for Phase 3, so it is **not**
  implemented here."
- Since TDD 3C established no mechanism at all for sandboxing arbitrary
  Python execution, TDD 3E §5's own "no new isolation technology beyond
  what TDD 3C already established" instruction has exactly one honest
  reading for an Agent Package's `handler.py` load: no isolation mechanism
  exists for it, full stop. Inventing one now would violate this
  milestone's explicit "do not invent a sandbox mechanism if the
  repository and TDD do not specify one."
- Doc 12 §8's own execution-backend table clarifies *what* the Sandbox
  Test Run step is actually supposed to gate: doc 12 §6's flowchart labels
  it "Sandbox test run — trusted-execution-backend promotion gated on
  this." Doc 12 §8 explains "promoted out of sandboxed trust" as the
  `inprocess`/`subprocess` → `container` transition (Docker/Firecracker
  isolation, "required before an agent is promoted"). Phase 3 implements
  `inprocess` only — there is no second backend to promote into or avoid.
  The gate is real (it runs, and it can fail an install), but in Phase 3
  it has nothing to decide *between*, leaving structural handler
  conformance as the only currently meaningful thing it can check.
- `14-3e-agent-os-research.md` §8a (the `nova-auth` resolution) contains
  the clearest direct statement of where this project's actual security
  boundary lives: *"the real, binding security gate for Phase 3D is
  ADR-032's identity-confidence check"* and, for `capability-engine`,
  *"the real binding security boundary is its own OS-level sandboxing
  (its TDD §10's own opening line: 'This TDD **is** a
  security-boundary-defining TDD — §3's sandboxing mechanisms are the
  enforced boundary.')"* An agent's own dangerous work (filesystem writes,
  terminal execution, git operations) is always delegated through
  `action-engine` to `capability-engine`'s adapters (TDD 3E §9's
  agent-behavior table) — enforced at **execution time**, downstream of
  the Registry entirely. The Registry's own install-time Sandbox Test Run
  was never the place this project puts its actual enforcement boundary.

### What this means going forward

The Sandbox Test Run stage is real and meaningful (a handler that fails to
import, or whose `Handler` class does not satisfy `AgentHandler`, is
correctly refused registration) but is explicitly *not* a behavioral or
execution security boundary — that boundary is, and by design remains,
`capability-engine`'s own adapter-level OS scoping, exercised at
`action.execute()` time. This is now the documented conclusion for the
Phase 3E Gate Review; no code changes accompany it.

---

## Summary

| Item | Conclusion | Action |
|---|---|---|
| A. Registry idempotency key | Genuine architectural conflict between doc 12 and the already-approved Fork 3E-2 concrete ORM; also a real schema-type mismatch already present between Kernel's `agent_package_id: UUID` (Milestone 2) and Registry's `AgentPackage.id: str` (Milestone 3) | **Resolved 2026-08-23 by explicit user decision (option 2: revert to the approved ORM as specified).** Implemented across domain model, ports, repository, migration, pipeline, and tests — see §A's "Resolution" subsection. |
| B. Registry Sandbox Test Run | Structural `AgentHandler` conformance is the intended, correct Phase 3 scope; no behavioral isolation is specified or required | **Resolved as documented.** Milestone 3's implementation already matches this conclusion; no code change required. |
