# Phase 3E — `agent-os`: Gate Review (structure only — not yet applicable)

**Status: PENDING. Research and decision pass complete
(`docs/design/phase-3/14-3e-agent-os-research.md`); no implementation
exists; no acceptance criteria have been verified; no CI, Trivy, or
real-infrastructure results exist to report. This document is a
placeholder structure only, prepared ahead of implementation per the
established Gate Review convention — it is explicitly NOT a completed
review, and its final gate status (§9) is explicitly NOT "Go."**

This structure mirrors the shape used by every prior Phase 3 Gate Review
(`phase-3a-gate-review.md`, `phase-3b-domain-foundation-gate-review.md`,
`phase-3b-decomposition-orchestration-gate-review.md`,
`phase-3c-capability-engine-gate-review.md`,
`phase-3d-action-engine-gate-review.md`) so that once implementation
happens, filling it in follows the same discipline every other Phase 3
sub-phase already used — not so that any section below can be read as
current fact today. Every section is explicitly marked pending; none is
filled in with fabricated data.

---

## 0. Scope executed

**Not yet executed.** Planned scope, per
`docs/design/phase-3/08-tdd-3e-agent-os.md` §0: `agent-os/{kernel, sdk/python,
registry, supervisors}`, the five Agent Packages (`research-agent`,
`coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent`), the
`engineering` Supervisor, and the `GoalsPort` real-RPC migration in both
`reasoning-engine` and `executive-cognition-engine`.

## 1. Architectural decisions

**Originally: not yet approved.** Four forks (3E-1 through 3E-4) and one
additional, previously-undisclosed dependency question (`packages/nova-auth`)
have recommended resolutions in
[`14-3e-agent-os-research.md`](../../design/phase-3/14-3e-agent-os-research.md)
§3-§9 — none is approved. This section will record each decision's
final, approved form once the user has approved it, the same way Phase
3D's own Gate Review §1 recorded §5.1-§5.3's approved decisions only
after approval, not before.

**Update (2026-08-19), additive.** All four forks (3E-1 through 3E-4) are
now **approved**, and the two remaining open items (`nova-auth` scope,
`priority`'s critical-path-position formula) are **resolved** — full
record in `14-3e-agent-os-research.md` §9/§8a/§8b and
`08-tdd-3e-agent-os.md` §11. This is an approval of the **architectural
decisions only** — it does not authorize starting Phase 3E's own
implementation PR (a separate approval, not yet given), and it does not
change this Gate Review's own overall PENDING status: §2 through §10
below still correctly report no code, no tests, no CI, and no
real-infrastructure results, because none exist yet.

## 2. Contracts added

**None yet.** Planned, per the research document: `AgentResult`,
`AgentContext`, `AgentHealth`, `AgentMetrics` (`nova_contracts.entities`);
`AgentMessage`, `AgentMessageType`, `agent_os.health.snapshot`,
`agent_os.task.completed` (`nova_contracts.events.agent_os`, new module);
`planning.goals.current.request`/`.reply` (`nova_contracts.events.planning`,
additive).

## 3. Persistence

**None yet.** Planned, per the research document §4: a new `agent_os`
Postgres schema (`agent_instance`, `agent_package` tables), following the
same per-engine-schema, natural-key-idempotency pattern already
established by `action-engine`/`capability-engine`/`planning-engine`.

## 4. Testing and verification results

**Not applicable — no code exists to test.** No test count, coverage
figure, or pass/fail result is reported here, and none should be, until
implementation exists. This section will use the same table format every
other Phase 3 Gate Review uses (`-m "not real_infra"` unit/contract/
integration counts, coverage percentage vs. the 85% gate, real-Postgres
restart-survival results) once there is something real to report.

## 5. CI results

**Not applicable.** No PR has been opened; no GitHub Actions run exists
for Phase 3E.

## 6. Trivy results

**Not applicable.** No `Dockerfile` for any Phase 3E component exists yet.

## 7. Real-infrastructure results

**Not applicable.** No repository layer exists to verify against real
Postgres; no real end-to-end path (Reasoning → Planning → NAOS → Kernel →
Supervisor → Agent Packages → peer review → Action Engine → real git
commit) has been exercised.

## 8. Known limitations

Not applicable until implementation exists. **Update (2026-08-19),
additive:** the six items originally tracked as open, unresolved scope
questions in `14-3e-agent-os-research.md` §9 are now all resolved/approved
(see that document's §9 and §1 above) — none remain pending. The most
consequential resolved item for future limitations reporting: `nova-auth`
permission enforcement is declared-intent-only in Phase 3E (§8a of the
research document), the same accepted gap already disclosed for
`capability-engine` and `action-engine` — this will be the first "known
limitation" recorded here once implementation exists to report against.

## 9. Acceptance criteria

Reproduced from `docs/design/phase-3/08-tdd-3e-agent-os.md` §14
(itself quoting `ENGINEERING_ROADMAP.md:542-546` as the binding spec) —
**status column intentionally left blank; none has been attempted yet:**

| # | Criterion | Status |
|---|---|---|
| 1 | A non-trivial multi-step coding objective produces a correct Task Graph, executes via at least two agent instances working in parallel where dependencies allow, includes at least one real peer-review round, and produces a verifiable result. | Not attempted |
| 2 | Killing `agent-os-kernel` mid-execution and restarting resumes in-flight Task Graph work rather than restarting it from scratch. | Not attempted |
| 3 | Installing `coding-agent@1.1.0` → `1.2.0` hot-loads without a kernel restart and without dropping in-flight instances of the old version. | Not attempted |
| 4 | `GoalsPort`'s real-RPC migration is provably transparent to both calling engines. | Not attempted |
| 5 | Every one of the five agents' manifest validates against `AgentHandler` before the Registry will register it. | Not attempted |

## 10. Final gate status

**Not Go. Not Conditional. Not applicable in either sense — there is
nothing yet to gate.** This section exists only so the document's
structure matches every other Phase 3 Gate Review's own section numbering;
it will be filled in with an actual gate status only once implementation,
tests, CI, Trivy, and (where applicable) real-infrastructure verification
all exist to support one. **No implementation branch or PR has been
created. Phase 3E has not started.**
