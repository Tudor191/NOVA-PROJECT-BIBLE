# Architecture Review Report — Phase N: <Phase Name>

> Copy this file to `phase-N-<slug>.md` in this directory when a phase completes.
> Required for every phase from Phase 1 onward (user directive). No phase is
> considered complete without this report filed alongside its merged implementation.

**Phase:** N — <name>
**Completed:** <date>
**Design document(s):** <link to docs/design/phase-N/ if one exists>
**Author:** <who/what produced this — for an AI-assisted phase, say so explicitly>

## 1. What was implemented

Concrete, verifiable list: which services/packages, which endpoints, which events,
which tables/graph schemas. Link to the actual merged code, not just the design doc
— this section documents what shipped, which may differ from what was designed if
the design changed during implementation (and if it did, say where and why).

## 2. Why each architectural decision was made

For every non-obvious choice made *during implementation* (as opposed to already
decided in the design doc or an existing ADR): what was chosen, what the alternative
was, and why this one won. Reference existing ADRs by number rather than
re-explaining them; this section is for decisions the design doc didn't already
settle.

## 3. Tradeoffs considered

What was explicitly traded away, and why that trade was acceptable *for this phase*.
Every tradeoff should be phrased so a future reader can tell whether the conditions
that made it acceptable still hold.

## 4. Known limitations

What the shipped implementation does not do, deliberately or otherwise. Distinguish
"deliberately out of scope for this phase" (with a pointer to which future phase
picks it up) from "should probably be fixed but wasn't blocking."

## 5. Technical debt introduced, if any

Be specific: file/module, what shortcut was taken, what the correct fix looks like,
and a rough sense of cost/urgency. "None" is an acceptable answer if genuinely true
— don't manufacture debt to fill the section, and don't omit real debt to avoid
admitting it.

## 6. Future improvements

Concrete, not aspirational. Each item should be actionable by a future phase or a
follow-up task, not a vague "could be better."

## 7. Risks

What could go wrong because of this phase's design, at what likelihood/impact, and
what (if anything) mitigates it today. Include operational risks (what happens under
load, what happens if a dependency is unavailable) as well as architectural ones.

## 8. Compatibility with the NOVA Project Bible

Explicit traceability: which Bible Part(s) this phase implements, and an honest
assessment of how faithfully. If any Bible requirement was deliberately deferred,
simplified, or reinterpreted (as Phase 0/1's ADRs have done in a few places), list
it here even if it's already recorded as an ADR — this section is the single place a
reviewer can check "does the current state of the system still match the Bible"
without cross-referencing every ADR individually.

## Sign-off

- [ ] All items in the phase's design-doc review checklist (if one exists) are
      either satisfied or explicitly noted as changed, with reasoning above.
- [ ] The phase's Definition of Done ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met for every PR in this phase.
- [ ] The per-subsystem deliverable checklist ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was met for every subsystem this phase touched.
