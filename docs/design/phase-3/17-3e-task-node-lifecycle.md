# 17 — Phase 3E: TaskNode lifecycle ownership, admission, and the ready→running hand-off

**Status:** APPROVED (2026-08-29). Implemented in the TaskNode-lifecycle
slice (Slice 1 of the five-slice §14 criterion #1 programme).

**Scope:** who owns each `TaskNode.status` transition, when a freshly
decomposed graph becomes dispatchable, how a completion advances the graph,
and the exact transaction/event ordering that keeps the Kernel from
dispatching the same node twice.

**No new contracts, event subjects, RPCs, or migrations.**
`AgentOsTaskCompletedPayload` is untouched — no new `outcome` value, no new
field. `planning.task_graph.created` and the existing transactional outbox
carry everything.

---

## 1. The defect this closes

The real Reasoning → Planning → Kernel path dispatched **zero** agent
instances, for any objective, no matter how good the Task Graph.

Verified in source, then empirically:

| Step | Evidence |
|---|---|
| `TaskNode.status` defaults to `"pending"` | `planning-engine/domain/models.py` |
| `decompose()` never overrode it | `domain/decomposition.py` |
| `node_snapshot()` copies `status` through verbatim | `events/snapshot.py` |
| The Kernel Scheduler skips every non-`"ready"` node | `agent-os/kernel/domain/scheduler.py` — `if node.status != "ready": continue` |
| Nothing ever set a node `"ready"` at creation | `reset_node_status` was the only status writer, called from one site, for `interrupted`/`failure` only |

A probe of the real `decompose()` against a two-node coding+qa graph
produced correct categories, a correct dependency edge, a valid critical
path — and **0 ready nodes**.

Every pre-existing full-loop test hand-built `TaskNodeSnapshot(...,
status="ready")`, which is exactly the construction the §14 criterion #1
end-to-end test is forbidden to use. That fixture masked the gap in every
earlier slice.

A second, related gap: nothing marked a node `"completed"` on success and
nothing promoted its dependents, so even a graph that *could* start could
never advance past its first layer — while criterion #1 demands a
"non-trivial **multi-step**" objective.

## 2. Ownership

**Planning Engine owns every `TaskNode.status` transition. The Kernel owns
execution and dispatch and never writes planning state.**

This is the documents' own split, not a preference imposed here:

- **TDD 3B §6.1** — "`planning-engine` subscribes to mutate the
  corresponding `TaskNode.status`".
- **TDD 3E §4** — "its `assigned_task_node_id` is reset to `"ready"` **in
  `planning-engine`** (via the same event path §7 uses)".
- **TDD 3E §12** row 1 — the crashed instance's `TaskNode` "reverts to
  `"ready"` for redispatch", again through `agent_os.task.completed`.

**TDD 3E §4:140 defines what `"ready"` means:** "for each `TaskNode` with
`status="ready"` **(all `depends_on` complete)**". `"ready"` is therefore a
*derived predicate over the graph*, not a free-standing state — which is
why `admit`/`promotable_ids` live in `domain/task_graph.py` alongside
`compute_critical_path`, as structural queries.

## 3. State-transition table

| # | Trigger | Precondition | Transition | Authority |
|---|---|---|---|---|
| 1 | Graph creation | `depends_on == []` | → `ready` | TDD 3E §4:140 |
| 2 | Graph creation | `depends_on != []` | → `pending` | same |
| 3 | Hand-off, same txn | `status == "ready"` | `ready` → `running` | §5 below |
| 4 | `agent_os.task.completed` `success` | node not terminal | → `completed` | TDD 3B §6.1 |
| 5 | …same event, cascade | every dep now `completed` | `pending` → `ready` | TDD 3E §4:140 |
| 6 | `needs_revision` | node not terminal | → `ready` | peer review asked for another round |
| 7 | `interrupted` | node not terminal | → `ready` | TDD 3E §4/§12 |
| 8 | `failure` | node not terminal | → `failed` (terminal) | §4 below |
| 9 | any outcome | node already `completed`/`failed` | no-op | redelivery guard |

`blocked` remains unused in Phase 3 — no document assigns it a trigger.
Disclosed, not invented.

## 4. `outcome="failure"` is terminal — an explicit narrowing

**TDD 3E §12 does not define post-retry failure semantics.** Its failure
table has five rows; only one concerns an execution failure ("Agent
instance crashes mid-task"), and that row prescribes the *opposite* of a
terminal state — revert to `"ready"`. There is no row for "the agent failed
and the Kernel's retry path is exhausted", and no row anywhere in TDD 3E
produces a terminal `"failed"` `TaskNode`. TDD 3E contains no occurrence of
"retry" or "exhausted": the bounded single retry is authored by
`agent-os/kernel/domain/scheduler.py`'s own comment, not by any design
document.

This implementation therefore **narrows** §12's execution-failure behavior,
and says so rather than implying the documents settled it.

**What the narrowing rests on**, verified in source rather than assumed: by
the time `outcome="failure"` is published, the failed instance has already
been through `supervisor_port.plan_restart()` and the bounded retry.
`agent-os/supervisors/domain/restart.py::plan_restart` returns the failed
instance under all three strategies — `one_for_one` returns it directly;
`one_for_all`/`rest_for_one` filter only `status != "completed"`, and the
Kernel stamps the row `"failed"` before calling. The retry is therefore
always attempted and always exhausted first.

**Why terminal:** treating `"failure"` as `"ready"` after that point hands a
deterministically-failing node back to the Scheduler forever — dispatch,
fail, retry, fail, reset, dispatch — with no stopping condition anywhere in
the documents. This is proven directly by
`test_a_deterministic_failure_never_enters_an_unbounded_redispatch_loop`
and its unit-level counterpart.

This supersedes one line of the restart-resume slice (`b9aed32`), where
`failure` reset to `"ready"`. `"interrupted"` is unchanged.

## 5. The ready→running hand-off (Option C)

### The hazard

If a node stays `"ready"` while its instance executes, **any republish
re-dispatches it**. Republishes happen on every completion. With two ready
siblings A and B: A completes → republish → B is still `"ready"` → B is
dispatched a second time. Real double dispatch.

### Options considered

| Option | Mechanism | Cost |
|---|---|---|
| A | Kernel publishes a new `agent_os.task.dispatched` subject | new contract + subject |
| B | Kernel skips nodes that already have an `agent_instance` row | no contract; dispatch-dedup state moves into the Kernel |
| **C (approved)** | Planning marks handed-off nodes `"running"` in the same transaction that enqueues the republish | **zero** new contracts, events, or RPCs |

### The ordering

Every write path that enqueues `planning.task_graph.created` performs these
steps, in this order, in **one** transaction
(`planning-engine/domain/ports.py::HAND_OFF_ORDERING` is the canonical
in-code statement):

```
1. apply the caller's node mutations (admission, or `transitions`)
2. build the outbox payload from the graph AS IT NOW STANDS  <-- "ready"
3. write the outbox row
4. UPDATE every still-"ready" node of this graph to "running"
5. COMMIT
```

**Step 2 always precedes step 4.** That single rule is the whole mechanism.

The published `TaskGraphSnapshot` is a **hand-off document**: it names the
nodes the Scheduler should pick up now, so those nodes must appear
`"ready"` in it. The committed rows say something different and equally
true — those nodes have already been handed over, so they are `"running"`.
Any later republish reads committed state, sees `"running"`, and cannot
re-offer work already in flight.

`"running"` therefore means **"handed to the Kernel"**, not "an asyncio
task is currently live". That is the honest reading under Phase 3's
synchronous `inprocess` backend, and it is the same reading TDD 3E §4's
restart reconciliation already assumes when it re-queues every `"running"`
row after a Kernel restart — recovering precisely a hand-off the Kernel
dropped.

## 6. Kernel-side `agent_instance` correctness

TDD 3E §4 specifies that restart reconciliation re-queues "every
`agent_instance` row still marked `status="running"`". **No such row was
ever written.** `spawn()` is synchronous, so `dispatch_task_node` inserted
rows already terminal (`"completed"`/`"failed"`), and a Kernel killed
mid-dispatch left nothing for `reconcile_running_instances` to find —
silently undercutting acceptance criterion #2.

Fixed by `_spawn_tracked`: the row is persisted `status="running"`,
`health_status="unknown"` **before** `spawn()` is awaited, then transitioned
to its terminal status afterwards. Because the instance id must exist before
the work starts, `AgentExecutionBackend` gains `next_instance_id()` and
`spawn(..., instance_id=...)` — the id stays the backend's to mint, since a
future `subprocess`/`container`/`remote` backend may need it to carry
backend-specific structure. `spawn()`'s existing callers are unaffected:
`instance_id` defaults to `None` and mints a fresh id.

## 7. Full event flow

```
reasoning.process.completed
  → decompose() → admit() → insert(graph, outbox_event_builder)
      [one txn, HAND_OFF_ORDERING steps 1-5]
  → outbox worker publishes planning.task_graph.created   [snapshot: ready]
  → Kernel dispatch_ready_nodes dispatches every "ready" node
      [agent_instance row written "running" before spawn()]
  → Kernel publishes agent_os.task.completed
  → resolve_transitions(...) → apply_transitions(...)
      [one txn, same ordering; completion + promotions are atomic]
  → outbox worker republishes → next layer dispatches
```

Terminates when no node is `"ready"` or `"pending"`.

## 8. What this does NOT change

- No new event subject. `agent_os.task.dispatched` was considered and
  explicitly rejected in favour of the hand-off ordering.
- No `nova_contracts` change. `TaskNodeSnapshot.status` already carries the
  full `pending|ready|running|blocked|completed|failed` vocabulary.
- No Alembic migration. `task_node.status` already exists and was already
  mutable.
- No TypeScript codegen change.
- No Kernel write into planning state, and no planning write into
  `agent_os` state — ADR-004 boundaries unchanged.

The only signature changes are engine-internal: `PlanningRepository.insert`
becomes builder-style (matching `append_nodes`/`apply_transitions`'
long-standing convention), `reset_node_status` generalises to
`apply_transitions`, `KernelRepository.update_status` gains an optional
`health_status`, and `AgentExecutionBackend` gains `next_instance_id()`.

## 9. Related, still open

Slices 2–5 of the same programme, each separately approved and not yet
implemented: real parallel dispatch (`asyncio.gather`), `requested_by` as
the primary user id for the ADR-032 gate, relative-path resolution against
`sandbox_filesystem_root`, `TerminalAdapter` default cwd and PATH,
`coding-agent` git add + commit, and the criterion #1 real-path E2E test.
