# Phase 4 Design — Perception, Autonomy & Digital Twin

*(Added 2026-10-16. Protocol §6.1 and §7.1 check every phase design package's
README; until now this package had none — closure-matrix finding N-05.)*

Phase 4 makes the backend reachable from a browser and adds what the
[roadmap](../../roadmap/ENGINEERING_ROADMAP.md) calls *Perception, Autonomy &
Digital Twin*. The Bible Parts it implements:

- [Part 6](../../bible/part-06-nova-cognitive-state-engine.md), the Cognitive State Engine;
- [Part 11](../../bible/part-11-perception-engine.md), Perception, extended;
- [Part 14](../../bible/part-14-autonomy-engine.md), Autonomy;
- [Part 16](../../bible/part-16-digital-twin-engine.md), the Digital Twin, extended.

Its scope, acceptance criteria AC-1 … AC-8, carry-forwards, decisions and branch
workflow are in [`00-master-scope.md`](00-master-scope.md).

**Status is not repeated here, so it cannot go stale here.** The authoritative
status of every document is the table in master scope §17, *Documents in this
package*. Phase completion lives in the Gate Reviews and Slice Completion
Records under [`docs/roadmap/architecture-reviews/`](../../roadmap/architecture-reviews/),
and in [`docs/project-health/`](../../project-health/).

## Documents

| Document | Milestone | Subject |
|---|---|---|
| [`00-master-scope.md`](00-master-scope.md) | Phase 4 | Goal, AC-1 … AC-8, milestones 4A–4F, carry-forwards CF-1 … CF-12, decisions, risks, non-goals, branch workflow |
| [`01-tdd-4a-gateways-and-web-client.md`](01-tdd-4a-gateways-and-web-client.md) | 4A | `api-gateway`, `ws-gateway`, `@nova/ui`, `apps/web-client` |
| `02-tdd-4b-observability-panels.md` | 4B | **Never written.** The 4B Gate Review records that (its l.462); see the note below |
| `03-tdd-4c-agent-os-api-and-containerization.md` | 4C | **Never written; waived at Phase 4C closure, 2026-09-12** (master scope §17) |
| [`04-tdd-4d-autonomy-engine.md`](04-tdd-4d-autonomy-engine.md) | 4D | `autonomy-engine`: the binding gate order, Policy Engine, Permission Matrix, the panel |
| [`05-tdd-4e-digital-twin-extension.md`](05-tdd-4e-digital-twin-extension.md) | 4E | `digital-twin-engine`'s extension to Part 16's domains |
| [`06-tdd-4f-companion-and-cognitive-state.md`](06-tdd-4f-companion-and-cognitive-state.md) | 4F | `nova-companion`, the perception extension, `cognitive-state-engine`, Autonomy Level 2 |
| [`07-tdd-4f3-nova-companion.md`](07-tdd-4f3-nova-companion.md) | 4F.3 | The companion's Cargo workspace and filesystem sensor |
| [`08-tdd-4f4-identity-confidence-policy.md`](08-tdd-4f4-identity-confidence-policy.md) | 4F.4 | CF-9's write surface for `IdentityConfidencePolicy` |
| [`09-tdd-4f5-autonomy-level-2.md`](09-tdd-4f5-autonomy-level-2.md) | 4F.5 | Level 2: selectable, policy-permitted, executing |
| [`10-tdd-4f6-initiative-trigger.md`](10-tdd-4f6-initiative-trigger.md) | 4F.6 | The initiative trigger, `autonomy.decision.requested` |
| [`11-tdd-4f7-cognitive-state-panel.md`](11-tdd-4f7-cognitive-state-panel.md) | 4F.7 | The read-only `/v1/cognitive-state` surface and its panel |
| [`12-tdd-4f8-acceptance-verification.md`](12-tdd-4f8-acceptance-verification.md) | 4F.8 | AC-7 and AC-8 against the deployed stack |
| [`13-tdd-4fp-production-promotion.md`](13-tdd-4fp-production-promotion.md) | 4F.P | Production thought ingestion, promotion and real execution |
| [`14-subsystem-flows-and-components.md`](14-subsystem-flows-and-components.md) | Phase 4 | SAD 15 §9.1 items 2 and 3 for the eight Phase 4 subsystems, **drawn after implementation** |

**The 4B TDD.** Master scope §17 still lists `02-tdd-4b-…` as *"not yet
written / Planned"*. That has been untrue as a plan since 4B merged. Unlike
4C's, it was never waived: the 4B Gate Review disclosed its absence and named
master scope §5–§6 and D-8 as 4B's acceptance source instead. Whether to waive
it on the record, as 4C's was, is the owner's decision (closure matrix, N-14).
Master scope §17 also has no row for document 14 or for this README. Both rows
wait for PR #42, which edits the same table, so the two changes do not collide.

*(2026-10-26.)* PR #42 has merged, as `43c6b12` on 2026-10-23. It did not
add either row, so §17 still has neither. Adding them means editing master
scope, which is outside this pull request's three files. That edit needs the
owner's authorization (closure matrix, N-05 and N-14).

*(2026-10-26, later.)* The owner authorized it, and PR #53 adds both rows to
master scope §17. N-05 and N-14 stay open. So does D-A13, the 4B waiver, and
§17's `02-tdd-4b-…` row is unchanged.
