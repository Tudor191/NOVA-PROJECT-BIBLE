# 16 — Phase 3E Hot-Load (Acceptance Criterion #3): Option A Design Decision

**Status: approved by explicit user decision (2026-08-28) and implemented.**
This document records the design pass that preceded implementation of TDD 3E
§14 acceptance criterion #3, and the exact scope boundary that decision sets.
It does not propose new architecture and does not reopen any of the six
approved Phase 3E decisions.

---

## 0. The criterion, verbatim

TDD 3E §14, criterion 3 (itself quoting `ENGINEERING_ROADMAP.md:544` as the
binding spec):

> Installing `coding-agent@1.1.0` → `1.2.0` hot-loads without a kernel
> restart and without dropping in-flight instances of the old version.

`docs/architecture/12-agent-architecture.md` §6 gives the same requirement
its fuller architectural framing:

> **Multiple versions coexist.** The Registry can hold `coding-agent@1.2.0`
> and `coding-agent@1.3.0` simultaneously; the Kernel Scheduler selects a
> version per policy (latest-stable by default...).
>
> **Hot load/unload.** Installing, upgrading, or removing an agent package
> never requires restarting `agent-os-kernel`. In-flight instances of the
> *old* version finish under supervision; new assignments route to the *new*
> version once it reports healthy.

---

## 1. The finding that shapes the decision

Two facts about Phase 3's own already-built, already-approved architecture
determine what "hot-load" can mean here, and both were verified directly
against source during the design pass:

**(a) Handler code is resolved by category, never by version.**
`agent-os/kernel/src/nova_agent_os_kernel/domain/execution_backend.py::
InprocessExecutionBackend.spawn()` resolves an instance's code as
`self._agents_root / manifest_id / "src" / "handler.py"` — one physical file
per agent package directory. `agent-os/registry`'s own
`domain/discovery.py::discover_agent_packages()` confirms the corresponding
layout: one `agents/<name>-agent/` directory per agent, containing exactly
one `agent.yaml` and one `src/handler.py`. **No per-version code storage
exists anywhere in this monorepo**, and doc 12 §3's own package layout does
not describe one.

**(b) There are no long-lived instances in Phase 3.**
`domain/models.py::AgentInstanceHandle`'s own docstring records the approved
design: Phase 3's `inprocess` backend runs an instance's *entire* assigned-task
lifecycle (`on_load` → `on_assign` → `execute` → `self_validate` →
`on_unload`) **synchronously inside `spawn()` itself**, returning only once
the instance has already finished. `AgentExecutionBackend.send()` raises
`NotImplementedError` for exactly this reason, and `terminate()` is a
documented no-op ("there is no live background task left to terminate").

**Consequence.** In Phase 3, at any instant, a category has at most one
instance actually executing, and that execution is already complete before
any caller could observe the handle. There is no window in which two
different code bodies for one category could be running concurrently —
not because of a defect, but because the approved Phase 3 execution model
has no concurrency mechanism yet (doc 12 §7's "Parallel dispatch" is
`already-designed-for`, not shipped, per doc 12 §15's own table).

---

## 2. The decision: Option A — metadata/scheduling-level hot-load

**Approved (2026-08-28).** Criterion #3 is satisfied at the Phase 3
architecture level through **`AgentPackage` version pinning and scheduling
metadata**, not through simultaneous execution of different bytecode
versions.

Stated plainly, so no future reader mistakes this document's scope:

> **This is version pinning and scheduling hot-load. It is NOT simultaneous
> execution of different bytecode versions.** Installing `coding-agent@1.2.0`
> alongside `1.1.0` changes which `agent_package` row a *new* dispatch
> resolves and pins itself to; it does not, and in Phase 3 cannot, cause an
> already-dispatched instance to keep executing a different copy of
> `handler.py`, because only one copy of `handler.py` exists per agent
> package and every instance's execution has already completed by the time
> the new version is installed.

What criterion #3's own five sub-requirements therefore mean here, precisely:

| Requirement | How Option A satisfies it |
|---|---|
| 1.1.0 installed and healthy | Unchanged existing behavior — the install pipeline's stage 8 promotes `health_status` to `"healthy"` after a successful `on_load`. |
| Existing in-flight instances continue against 1.1.0 | `agent_instance.agent_package_id` is written once at dispatch and **never mutated by any code path**. An existing row keeps pointing at 1.1.0's UUID permanently. |
| 1.2.0 installs without restarting Kernel | Registry's `insert()` enforces only `UniqueConstraint("category", "version")` — a second version is an ordinary insert. Kernel reads Registry over the Event Bus per dispatch, holding no cached package state, so nothing in Kernel needs restarting. |
| New dispatches select 1.2.0 | The `agent_os.registry.find_healthy_package.request` handler selects the **highest healthy version** by dotted-integer comparison. |
| Old instances not migrated/interrupted/invalidated | Nothing writes to `agent_instance` during install. Proven by an explicit test asserting the pre-install row is byte-for-byte unchanged afterwards. |

**Option B (per-version filesystem directories,
`agents/coding-agent/versions/1.1.0/src/handler.py`) was considered and
explicitly rejected** for this phase: it would require changing the Agent
Package layout, `tools/scaffold-agent-package.py`, discovery, and both
`_load_handler_class` call sites, and none of criterion #3's own
sub-requirements ask for differing *behavior* between versions — only that
old instances are untouched and new ones route correctly.

---

## 3. Selection policy, as approved

1. **Only `health_status == "healthy"` is selectable.** `"degraded"`,
   `"unhealthy"`, and `"unknown"` are all non-selectable. No `degraded`
   fallback semantics are invented — nothing in this codebase produces
   `"degraded"` today (the install pipeline writes only `"unknown"` at
   Registration and `"healthy"` after a successful `on_load`).
2. **Highest healthy version wins**, compared by dotted-integer tuple
   (`(1, 10, 0) > (1, 9, 0)`), **not** by `installed_at`. This is correct
   even if installs happen out of chronological order — e.g. a rollback
   re-install of an older version must not out-rank a newer one merely by
   being installed more recently.
3. **Fallback is automatic**: if the newest version is not healthy (e.g.
   1.2.0 installed but its `on_load` failed, leaving `"unknown"`), the
   highest *healthy* older version (1.1.0) is selected. Before this change,
   the handler returned `None` in exactly that case — a real defect this
   slice fixes.
4. **No healthy version at all → `None`**, unchanged.

**Permission Review's own `find_latest_by_category` semantics are
deliberately left untouched.** That method means "most recently
*installed*," which is the correct question for diffing a new install's
`required_permissions` against its predecessor (TDD 3E §5), and is a
*different* question from "which version should a new dispatch use." The two
are now explicitly separate concerns with separate repository methods.

---

## 4. Schema and contract impact

**No schema changes.** `id`, `category`, `version`, and `health_status`
already exist on `agent_package` and already suffice; `agent_instance.
agent_package_id` already pins an instance to an exact installed row (an
already-approved Fork 3E-2 column, present since Milestone 2).

**No contract changes.** `AgentOsFindHealthyPackageRequestPayload`
(`category` in) and `AgentOsFindHealthyPackageReplyPayload` (one
`AgentPackageSnapshot` out) are both sufficient as-is — the change is
entirely in *which* row the Registry-side handler chooses to answer with.

One **disclosed docstring correction** accompanies this change:
`AgentOsFindHealthyPackageRequestPayload`'s own docstring previously read
*"'candidates,' scoped to Phase 3's one-healthy-version-per-category
reality, resolves to 'the most recently installed healthy row'"* — that
sentence describes the pre-hot-load behavior and is now stale. It is
corrected in place to describe highest-healthy-version selection. This is a
comment-only edit to an existing payload; no field, name, or wire shape
changes.

---

## 5. What remains out of scope (disclosed, not silently omitted)

- **Uninstall / package removal.** `RegistryRepository` has no delete method
  and none is added here. Doc 12 §6's "hot load/**unload**" names removal as
  part of the same mechanism; only the load/upgrade half is in criterion #3
  and only that half is built. An old version's row is structurally
  permanent in Phase 3.
- **Zero-in-flight-instances cleanup.** Nothing archives or garbage-collects
  a superseded version's row once nothing references it. Criterion #3 does
  not ask for this, and no document defines a retention policy.
- **Registry scoring beyond version+health.** Doc 12 §6's "Scoring feeds
  scheduling" (historical success rate, average execution time, resource
  efficiency, per `AgentMetrics`) is a real, named, future capability with
  no persistence today — `agent_package` stores no metrics columns. Version
  and health are the only selection inputs in Phase 3. Unchanged by this
  slice, restated here so the gap stays visible.
- **Per-project version pinning.** Doc 12 §6 names "pinned per-project where
  required" alongside latest-stable-by-default. No project-scoped pinning
  mechanism exists anywhere in Phase 3 (no project entity reaches the Kernel
  Scheduler), so only the latest-stable default is implemented.
