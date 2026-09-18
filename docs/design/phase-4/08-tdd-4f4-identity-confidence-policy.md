# TDD 4F.4 — CF-9's write surface
## The missing write path for `IdentityConfidencePolicy`, in the engine that owns it

**Status:** **RATIFIED 2026-09-18 (§16).** All four questions are answered; §16
records each decision and what it forbids. *(This line read "DESIGN PREPARATION.
NOT RATIFIED. §15 lists four questions that must be answered before
implementation begins." until the ratification — preserved per protocol §0.3.4.)*
**Date:** 2026-09-18
**Branch:** `phase-4f4-tdd`, cut from `phase-4f.3` at `41f783a04a5170cade2c74e8342ff75509cb9435`
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines,
read from `origin/main` and verified in this session.

**This is a slice TDD, subordinate to
[TDD 4F](06-tdd-4f-companion-and-cognitive-state.md).** 4F is one milestone with
eight slices (TDD 4F §18); this document does not replace it, restate its
ratified decisions, or reopen anything it settled. Where the two disagree, TDD 4F
governs and the disagreement is recorded in §15 rather than resolved here.

**Why the branch is cut from `phase-4f.3` rather than `phase-4`:** 4F.3 is closed
but **PR #32 is not merged**, so `phase-4` does not yet contain the 4F.3
completion record this document cites. Cutting from `phase-4` would produce a TDD
whose own citations are absent from its own branch.

---

## 1. Purpose and scope

TDD 4F §18's row for this slice, verbatim:

> **4F.4** | CF-9's write surface in `action-engine` | *Proves:* **Stage 3 can
> pass for LOW risk, fail-closed unchanged**

**One deliverable, and one proof.** 4F.4 adds the missing *write* path to a table
`action-engine` already owns, and changes nothing else.

### 1.1 Why this slice exists at all

`action-engine`'s pipeline stage 3 reads an identity-confidence threshold, and
**with no policy row the threshold is 1.0 at every risk level, including LOW**
(`domain/pipeline.py`, verified at this head):

```python
policy = await repository.find_identity_confidence_policy(action.requested_by)
threshold = 1.0  # absent-policy fails closed: require maximum confidence (TDD 3D §10)
if policy is not None and risk.value in policy.minimum_confidence_by_risk:
    threshold = policy.minimum_confidence_by_risk[risk.value]
```

`perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` caps a real
single-signal identity below 1.0, so **every action is denied at stage 3** until a
policy row can exist — and **nothing in the repository can create one.** Verified
at this head: the only non-read reference to `IdentityConfidencePolicy` anywhere
is a `real_infra` test inserting the ORM row directly. That is CF-9.

**The asymmetry is specific.** `autonomy-engine` *has* a policy write surface
(`GET/POST/PATCH/DELETE /v1/autonomy/policies`). `action-engine`'s
`IdentityConfidencePolicy` has none.

### 1.2 What 4F.4 is not

**4F.4 does not close CF-9.** TDD 4F §5.3 is explicit: *"4F implementing the
capability does not close CF-9, and no 4F document may record it as closed."*
This document records it as **OPEN**. See §13.

---

## 2. Dependencies

### 2.1 On existing architecture — all of it pre-existing

| Dependency | State at `41f783a` |
|---|---|
| `IdentityConfidencePolicy` domain model | **Exists** — `domain/models.py:46`. `user_id: UUID`, `minimum_confidence_by_risk: dict[str, float]` |
| Table `action.identity_confidence_policy` | **Exists** — `user_id UUID PRIMARY KEY`, `minimum_confidence_by_risk JSONB NOT NULL` |
| `IdentityConfidencePolicyORM` | **Exists** — `repository/models.py:91` |
| `find_identity_confidence_policy` | **Exists** — read path only, `ports.py:212`, `postgres_action_repository.py:220` |
| Stage 3's evaluation | **Exists** and is **not modified by this slice** |
| `api-gateway` `/v1/action` prefix | **Exists** — `domain/routing.py:126`, forwards the whole subtree to `action-engine`. **No new prefix, no gateway change** |
| `RiskLevel` | **Exists** — `nova_contracts.events.planning`, five values: `negligible`, `low`, `moderate`, `high`, `critical` |
| `Settings.primary_user_id` | **ABSENT in `action-engine`** — corrected 2026-09-18, having been asserted here before it was checked. The idiom exists in `perception-engine` and `autonomy-engine`, not this engine, so **4F.4 must add the setting**. It is a one-line, ADR-025-consistent addition that §5.2's *"Identity: resolved server-side from `primary_user_id`"* requires, mirroring `autonomy-engine`'s non-optional form |
| `action-engine` real-infra tier | **Exists** — in `real-infra-checks.yml`'s matrix, with `test_repository_real_postgres.py` |

**The write path is the only thing missing.** Every other component of CF-9's
closure condition 1 is already in place.

### 2.2 On 4F.1, 4F.2, 4F.3 — none

None of the three is on this slice's path. 4F.3's companion, the workspace
subject and the filesystem sensor are unrelated to `action-engine`'s policy
table. Stated because the slices are adjacent in the milestone, not because a
dependency was found.

### 2.3 What 4F.4 unblocks, without claiming

AC-8's *"auto-executes at Level 2 … for a low-risk case"* is denied at stage 3
today. 4F.4 makes it **possible** for that gate to pass. It does not make AC-8
pass: that also needs 4F.5 (Level 2 dispatch) and 4F.6 (the trigger), and the
acceptance run is **4F.8's**.

---

## 3. Authoritative source mapping

Every requirement below traces to a ratified document. Nothing here is inferred
from the slice number.

| Requirement | Source |
|---|---|
| The slice's contents and proof | TDD 4F §18, 4F.4 row |
| Owner, surface, identity, persistence, evaluation semantics, fail-closed | TDD 4F **§5.2** — the minimum-surface table, reproduced in §6 |
| CF-9 is a 4F dependency; write surface belongs to `action-engine`; no second store; CF-9 not closed by implication | TDD 4F **D-4F-2** (RATIFIED) |
| Ownership of `IdentityConfidencePolicy` does not move | TDD 4F §5.4; **D-4D-2** |
| What must hold before CF-9 is *ever* closed | TDD 4F **§5.3**, five conditions |
| *"a configurable identity-confidence threshold per privileged capability (or per capability class), never a single hardcoded system-wide threshold"* | [ADR-032](../../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md) decision point 2 |
| *"No threshold value is proposed here. Choosing the first one is a security decision"* | ADR-032, closing section |
| Server-side identity, no caller-supplied `user_id` | **ADR-025**; 4E's discipline; TDD 4F §5.2 |
| Stage 3 semantics byte-identical | TDD 4F **§22**'s consistency audit: *"Ownership unchanged; stage 3 semantics byte-identical; CF-9's surface added in the owning engine (§5.2)"* |
| CF-9's register entry and its history | [`00-master-scope.md`](00-master-scope.md) §4 |
| Slice produces a completion record with a ledger, not a Gate Review | Protocol **§0.1**, **§0.2** |

---

## 4. Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | **Write methods on the repository port and its Postgres implementation** — upsert and delete for `IdentityConfidencePolicy` | `action-engine` `domain/ports.py`, `repository/postgres_action_repository.py` |
| 2 | **HTTP surface** — read, upsert, delete the calling deployment's own policy | `action-engine` `api/identity_confidence_policy.py` (new module) |
| 3 | **Request/response schemas with validation** — bounded confidences, known risk keys | same module |
| 4 | **Router registration** and **`Settings.primary_user_id`** (absent in this engine — see §2.1) | `action-engine` `main.py`, `config.py` |
| 5 | **Tests** — unit, integration, and the real-Postgres evidence §11 requires | `action-engine/tests/` |
| 6 | **Ceiling drift guard** — asserts `action-engine`'s configurable maximum and `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING` agree, by reading both as source text so no engine imports another (§16.5) | `tools/tests/` |

**Six deliverables. No migration, no new table, no new model, no new ORM class,
no Event Bus subject, no gateway change.**

---

## 5. Architectural boundaries

| Boundary | 4F.4's position |
|---|---|
| **Ownership** | `action-engine` keeps sole ownership of `IdentityConfidencePolicy`. D-4D-2 and TDD 4F §5.4 both require this; the write path lands **in the owning engine**, which is what makes it compatible rather than contradictory |
| **Persistence** | The **existing** table. No new table, no second store, no duplicate model, **no migration** |
| **Evaluation** | Stage 3 is **not modified**. 4F.4 supplies rows; it does not change how they are read or compared |
| **Fail-closed** | **Unchanged.** Absent policy still means threshold 1.0 at every risk level. This is a *negative control* in §10, not an assumption |
| **Identity** | Server-side from `Settings.primary_user_id` only. The request model has **no `user_id` field**, so a caller-supplied identity is unrepresentable rather than rejected |
| **Event Bus** | **Not engaged.** No subject is published, consumed or registered. Subject count stays **119**, `PUBLIC_TOPICS` stays **18** |
| **Gateway** | `/v1/action` already exists and forwards the subtree. **`api-gateway` is not modified** |
| **Cross-engine** | None. `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING` is **read about, never touched**; ADR-032's gate reads that number and quietly strengthening it would weaken a security gate by the back door (TDD 4F §9) |
| **ADR-004 / ADR-006** | Not engaged — no engine-to-engine import, no broker client |

---

## 6. The contract

Reproducing TDD 4F §5.2's ratified minimum surface, then stating it concretely.

| §5.2 requirement | As specified here |
|---|---|
| Owner | `action-engine`, unchanged |
| Surface | *"Create/read/update a policy for a user: minimum confidence per risk level."* Fronted by the existing `/v1/action` prefix |
| Identity | Server-side, `primary_user_id` |
| Persistence | The existing table |
| Evaluation semantics | Byte-identical |
| Fail-closed | Unchanged |

### 6.1 Route shape — and why it is not `autonomy-engine`'s

`autonomy-engine`'s policies are a **collection** (`POST /policies`,
`PATCH /policies/{id}`, `DELETE /policies/{id}`). `identity_confidence_policy`
has **`user_id` as its PRIMARY KEY** — there is exactly **one row per user**, so
a collection shape with generated ids would misrepresent the schema and invite a
second row that the table cannot hold.

**Proposed** (subject to §15's A-4F4-2):

| Method | Path | Semantics | Status |
|---|---|---|---|
| `GET` | `/v1/action/identity-confidence-policy` | The deployment's own policy | `200`, or **`404`** when absent |
| `PUT` | `/v1/action/identity-confidence-policy` | **Idempotent upsert** of the whole map | `200` |
| `DELETE` | `/v1/action/identity-confidence-policy` | Remove the row, returning to fail-closed | `204`, or `404` when absent |

**`404` rather than an empty default on `GET`** is deliberate: "no policy" and "a
policy that happens to be empty" are different security states, and the first
means threshold 1.0 everywhere. A synthesized empty body would read as the
second.

### 6.2 Request and response schema

```
IdentityConfidencePolicyRequest:
    minimum_confidence_by_risk: dict[str, float]

IdentityConfidencePolicyResponse:
    user_id: UUID          # echoed from the server's own resolution, never accepted
    minimum_confidence_by_risk: dict[str, float]
```

**No `user_id` on the request**, for the reason 4F.2/4F.3 established: a field
that does not exist cannot be forged.

### 6.3 Validation — the security-relevant half

| Rule | Why |
|---|---|
| Every key must be a `RiskLevel` value (`negligible`, `low`, `moderate`, `high`, `critical`) | An unrecognised key is silently ignored by stage 3's `risk.value in policy…` lookup, so it would look configured while changing nothing |
| Every value must satisfy `0.0 <= v <= 1.0` | A value above 1.0 is unreachable and fails closed forever; a negative value disables the gate entirely |
| The map may be empty, and an empty map is **not** the same as no row | An empty map leaves stage 3 at 1.0 for every risk — the same effect as absent, reached deliberately |
| **No default threshold is written anywhere** | ADR-032: *"No threshold value is proposed here. Choosing the first one is a security decision."* See **A-4F4-4** |

---

## 7. Data flow

```
operator / panel
   → api-gateway  /v1/action/identity-confidence-policy      [existing prefix, existing auth]
   → action-engine  api/identity_confidence_policy.py
        user_id := Settings.primary_user_id                  [ADR-025, server-side]
        validate risk keys + confidence bounds
   → repository.upsert_identity_confidence_policy(...)
   → action.identity_confidence_policy                       [existing table, one row per user]

...later, on an unrelated request:

action.execute
   → action-engine pipeline stage 3                          [UNCHANGED CODE]
        repository.find_identity_confidence_policy(user_id)  [existing read]
        threshold := policy value for this risk, else 1.0
        deny if effective_confidence < threshold
```

**The two halves never call each other.** The write surface's only effect on
execution is the row it leaves behind, which is precisely why stage 3 needs no
change.

---

## 8. Event Bus implications

**None.** No subject is registered, published or consumed.

| Invariant | Required at closure |
|---|---|
| Registered Event Bus subjects | **119**, unchanged (counted from the runtime registry, not by grepping decorators — TDD 4F.3 §21.1) |
| `PUBLIC_TOPICS` | **exactly 18**, unchanged |
| New subjects | **0** |

A policy change is deliberately **not** announced on the bus in this slice.
Nothing consumes such an announcement, and inventing a subject for a
hypothetical consumer is the speculative work the scope rule excludes.

---

## 9. Security and privacy

| Concern | Position |
|---|---|
| **This slice weakens a security gate if done carelessly** | It is the write path to an authorization threshold. Every control below exists for that reason |
| Fail-closed | **Unchanged and proven by negative control** (W-3). Absent policy → 1.0 → denial |
| Identity | Server-side only. No caller-supplied `user_id`, structurally |
| Threshold values | **None invented.** No default, no seed, no migration insert. A deployment that installs nothing keeps the 1.0 fail-closed default |
| `SINGLE_SIGNAL_CONFIDENCE_CEILING` | **Unchanged at 0.75**, asserted. ADR-032's gate reads it; raising it to make an acceptance criterion pass would weaken the gate by the back door |
| Stage 3 | Byte-identical, asserted structurally |
| Browser reachability | Only through `api-gateway`'s existing `/v1/action` prefix and its existing auth. No new prefix, no new auth path |
| Audit | See **A-4F4-3**: whether a threshold change must be recorded in the append-only history is an open question, not silently answered |

---

## 10. Acceptance criteria

Measurable, defined before implementation. Each is a claim with a stated proof.

| # | Claim | Proof required |
|---|---|---|
| **W-1** | A policy row can be **created through the production HTTP surface** and read back by **`find_identity_confidence_policy` in real Postgres** | Real-infra test: real HTTP request → real repository → real table → real read. **Not** a direct ORM insert |
| **W-2** | With that row present, **stage 3 admits a LOW-risk action** whose identity confidence is at or above the configured threshold | Real-infra test driving the **real pipeline** at stage 3, not a re-implementation of the comparison |
| **W-3** | **Absent policy still denies**, at threshold 1.0, for the same LOW-risk action | Negative control, same test file. **This is the fail-closed proof and is mandatory** |
| **W-4** | A client-supplied `user_id` **cannot** reach the row | The request model has no such field; a body carrying one is accepted and ignored, and the stored row carries `primary_user_id` |
| **W-5** | Invalid input is **rejected, not stored** | `422` for an unknown risk key; `422` for a confidence outside `[0.0, 1.0]`; the table is unchanged after each |
| **W-6** | **Stage 3's evaluation code is unchanged** | Structural assertion over `domain/pipeline.py`'s stage-3 block, plus a zero-diff check against `phase-4` for that function |
| **W-7** | `SINGLE_SIGNAL_CONFIDENCE_CEILING` is **unchanged at 0.75** | Asserted directly; zero diff in `perception-engine` |
| **W-8** | **DELETE returns the deployment to fail-closed** | Write a permissive policy, verify admission, delete it, verify the same action is denied again |

**W-3 and W-8 are the two that matter most.** A write surface that quietly made
the system permissive would satisfy W-1 and W-2 and still be a defect.

### 10.1 Negative and security tests — defined before implementation

1. Absent policy → threshold 1.0 → LOW-risk action denied (W-3).
2. Policy deleted → the same action denied again (W-8).
3. Unknown risk key → `422`, nothing stored (W-5).
4. Confidence `1.5` and `-0.1` → `422`, nothing stored (W-5).
5. Body carrying `user_id` → that value never reaches the row (W-4).
6. Empty map stored → stage 3 still at 1.0 for every risk.
7. No new Event Bus subject; `PUBLIC_TOPICS` still 18.
8. `perception-engine` and `api-gateway` diffs are **empty**.
9. No migration file added; no ORM model added or altered.

---

## 11. Real-infrastructure requirements

`action-engine` is **already** in `real-infra-checks.yml`'s matrix, so this
slice adds no CI matrix row.

| Requirement | |
|---|---|
| **Mandatory tier** | W-1, W-2, W-3 and W-8 are **only decidable against real Postgres**. A fake repository would prove that the fake agrees with itself |
| Fixtures | The established `postgres_container` + `run_alembic_upgrade` pattern, as `test_repository_real_postgres.py` already uses |
| **The write must go through the production surface** | The existing test inserts `IdentityConfidencePolicyORM` directly. That is exactly what ADR-032 calls out as *not* an implementation, so 4F.4's evidence must not do the same |
| Stage 3 | Driven through the **real pipeline function**, not a re-implementation of the threshold comparison |

---

## 12. CI requirements for closure

| Evidence | Required |
|---|---|
| Real GitHub Actions run at the **exact implementation SHA** | Protocol §11.1 |
| `Build & Scan` | 22/22 built **and** Trivy-scanned; no new image expected |
| `Real-Infrastructure Checks` | 15/15, with `action-engine`'s job carrying the new tests |
| `PR Checks` | `checks` green — lint, mypy, import-linter, codegen zero drift, full suite |
| Skipped / cancelled | **Zero** |
| A PR | Opened only when the user asks (protocol §11.1) |

---

## 13. Deferred obligations

### 13.1 Owned by 4F.4

| # | Obligation | Why it is 4F.4's |
|---|---|---|
| **CF-9's *capability*** | The write surface itself | TDD 4F §18's 4F.4 row and **D-4F-2** |
| **L-15** | **Opened by this slice** — policy mutations are unaudited. Owner **`action-engine`**, settled at **4F closure** or on a separately ratified audit design (**D-4F4-3**, §16.3) | Ratified 2026-09-18 |

**That is the complete list.** No ledger row L-1…L-14 is dated to 4F.4 by any
authoritative document.

### 13.2 Explicitly NOT 4F.4's — ownership preserved unchanged

| # | Obligation | Owner, unchanged |
|---|---|---|
| **CF-9 itself** | **Stays OPEN.** TDD 4F §5.3: *"4F implementing the capability does not close CF-9, and no 4F document may record it as closed."* Its five closure conditions are §13.3 | Open beyond 4F.4 |
| **CF-10** | Trust Engine unavailable / fails closed. Untouched | Outside 4F |
| **CF-11** | The initiative trigger's producer | **4F.6** |
| **L-6** | README / *"a new engine now exists"* | **4F closure** |
| **L-11** | Fusion for workspace signals | **4F closure** (corrected in TDD 4F.3 §19.2) |
| **L-13** | `known_projects` population | **4F closure or later** |
| **L-14** | Filesystem consent policy | **4F closure**, or earlier if separately ratified |
| **L-1…L-5, L-8, L-9, L-10** | Gate Review, health record, master row, roadmap, SLOC tables, READMEs, sweeps | **4F closure** |
| **F-2** | SLOC scope ambiguity | **L-5**, at 4F closure |
| **Downstream world-model E2E** | Not moved. Remains **4F.8's** per TDD 4F §20.1 and §18 | **4F.8** |
| **AC-7 / AC-8 acceptance run** | **4F.8's** | **4F.8** |
| **Autonomy Level 2** | **4F.5's** | **4F.5** |
| **Digital Twin completion, Phase 4F closure** | Neither is 4F.4's | 4F closure |

**4F.4 absorbs none of these.** Each is listed so that absorption would be
visible rather than quiet.

### 13.3 CF-9's five closure conditions, and what 4F.4 can honestly supply

TDD 4F §5.3, verbatim conditions, with 4F.4's expected contribution:

| # | Condition | 4F.4 |
|---|---|---|
| 1 | A policy row can be created through a production surface **and** read back by stage 3 in real Postgres | **Satisfied** by W-1 + W-2 |
| 2 | The threshold is **per privileged capability or per capability class**, never a single hardcoded system-wide value | **See A-4F4-1** — unresolved, and the reason CF-9 cannot close here |
| 3 | Absent policy still fails closed at 1.0, proven by a negative control | **Satisfied** by W-3 |
| 4 | `SINGLE_SIGNAL_CONFIDENCE_CEILING` unchanged | **Satisfied** by W-7 |
| 5 | Phase 4B Gate Review §0.3, Phase 4C's health record and master scope §4's register each updated with the closing evidence | **Not 4F.4's** — those are category 3–5 documents, deferred by protocol §0.1 to **4F closure** |

**Conditions 2 and 5 cannot be met by this slice**, so **CF-9 stays OPEN**, as
§5.3 requires and as D-4D-2 ratified.

---

## 14. Non-goals

Each is named because it is adjacent enough to be assumed.

| Not in 4F.4 | Owning slice |
|---|---|
| Autonomy Level 2 dispatch | **4F.5** |
| The initiative trigger / CF-11 | **4F.6** |
| `/v1/cognitive-state` and the panel | **4F.7** |
| The AC-7 / AC-8 acceptance run | **4F.8** |
| Downstream world-model E2E | **4F.8** |
| A UI for editing the policy | Not in 4F at all — no slice row names one |
| Changing stage 3's comparison, ordering or fail-closed default | **Never.** Explicitly forbidden |
| Choosing a threshold value | **Nobody yet** — see **A-4F4-4** |
| Per-capability policy granularity | **See A-4F4-1** |
| A second store, a new table, a migration | **Never.** §5.2 |
| Closing CF-9 | **Not 4F.4's**, by §5.3 |
| Any Event Bus subject for policy changes | Not in scope; nothing consumes one |

---

## 15. Ambiguities requiring ratification

**Four. None is resolved in this document.** Implementation must not begin until
each is answered, because three of the four change what gets built.

### A-4F4-1 — Does a per-*risk-level* threshold satisfy ADR-032 decision point 2?

**The tension is real and textual.**

- **ADR-032 point 2**, verbatim: *"a configurable identity-confidence threshold
  **per privileged capability (or per capability class)**, never a single
  hardcoded system-wide threshold."*
- **The existing table** is keyed by **risk level**:
  `minimum_confidence_by_risk: dict[str, float]`.
- **The existing model's own docstring** asserts the equivalence: *"ADR-032 point
  2 — a configurable identity-confidence threshold **per risk tier**."*
- **TDD 4F §5.2** requires 4F.4 to use *"the existing table. No new table, no
  second store, no duplicate model."*
- **TDD 4F §5.3 condition 2** restates the closure test in ADR-032's words, not
  the table's.

So the ratified scope forces the per-risk shape, while the ratified *closure
condition* is phrased per-capability.

| Option | Consequence |
|---|---|
| **(a) Ratify "risk tier" as the capability class** — record it explicitly as the project's reading of ADR-032 point 2 | No code change. CF-9's condition 2 becomes satisfiable. **Recommended** |
| (b) Extend to per-capability granularity | Requires a new schema — **forbidden by §5.2**. Would be its own slice |
| (c) Leave unresolved, defer to CF-9 closure | 4F.4 still ships; CF-9 stays open on condition 2 indefinitely |

**Recommendation: (a).** Risk level *is* a classification of privileged actions,
which is what "capability class" describes, and it is the one canonical risk
scale in the project (Bible Part 14, reused verbatim). It is also what the
existing model already claims. **But this is a security-semantics ratification,
not an implementation detail, and I will not make it silently.** Under (c), 4F.4
is still buildable exactly as specified — only CF-9's eventual closure is
affected.

### A-4F4-2 — Route shape: single-resource `PUT` or collection `POST`/`PATCH`?

The table has **one row per user** (`user_id PRIMARY KEY`), but the established
in-repo precedent (`autonomy-engine`) is a collection.

| Option | Consequence |
|---|---|
| **(a) `GET`/`PUT`/`DELETE` on a single resource** | Matches the schema exactly; upsert is idempotent; no invented id. **Recommended** |
| (b) Mirror `autonomy-engine`'s collection shape | Consistent with the sibling surface, but invents an identifier the table does not have and implies a multiplicity it cannot store |

**Recommendation: (a).** Consistency with a schema beats consistency with a
differently-shaped sibling.

### A-4F4-3 — Must a threshold change be audited?

`action-engine` has an append-only `action_execution_history`. Changing an
authorization threshold is a security-relevant administrative act, and nothing
currently records it.

| Option | Consequence |
|---|---|
| **(a) No audit in 4F.4** | Smallest slice, matches §5.2's minimum surface literally. Leaves a real gap. **Recommended, with the gap ledgered** |
| (b) Write an audit row on every change | Beyond §5.2's *"and nothing more"*; needs a schema decision for a table that models action lifecycle, not admin actions |

**Recommendation: (a)**, and open a **new ledger row** recording that policy
mutations are unaudited — the honest disposition, rather than either silently
omitting it or quietly expanding scope. **I have not assigned a number**; per the
ordering rule the next free row is L-15, but that is the user's to ratify.

### A-4F4-4 — Who chooses the first threshold value?

ADR-032 closes with: *"**No threshold value is proposed here. Choosing the first
one is a security decision.**"*

4F.4 deliberately writes no default. But **4F.8's AC-8 run needs a real LOW-risk
row to exist**, with a number at or below the real identity confidence — which
`SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75` caps.

| Option | Consequence |
|---|---|
| **(a) No value anywhere in production; 4F.8's E2E writes one through the production surface, using a value ratified then** | Keeps the security decision explicit and out of the codebase. **Recommended** |
| (b) Ratify a LOW-risk default now and ship it as a seed | Puts a security decision into a migration, which ADR-032 warns against |
| (c) 4F.4's tests pick a number for test purposes only | Acceptable *for tests*, and orthogonal — it must never become a production default |

**Recommendation: (a), with (c) for test fixtures only.** The number a test
chooses must not appear in `src/`.

---

## 16. Ratified decisions — 2026-09-18

All four of §15's questions are answered. §15 is preserved exactly as written,
per protocol §0.3.4; this section records the decisions and what each forbids.

### 16.1 D-4F4-1 — risk tier **is** the capability class. **APPROVED (a).**

For ADR-032 decision point 2, **risk tier is the capability class** for
`IdentityConfidencePolicy`. **The existing risk-tier-keyed schema is
authoritative** and is the form CF-9's eventual closure evidence will cite.

**Forbidden:** capability IDs, a capability table, any new schema, any second
keying dimension.

### 16.2 D-4F4-2 — single-resource API. **APPROVED (a).**

```
GET    /v1/action/identity-confidence-policy
PUT    /v1/action/identity-confidence-policy
DELETE /v1/action/identity-confidence-policy
```

`user_id` stays **server-derived** from the trusted caller context. **A
client-supplied `user_id` is never an authoritative identity.** `GET` with no
policy returns **404**. `DELETE` restores the fail-closed state.

**Forbidden:** an invented collection id, a caller-supplied identity, a
synthesized empty policy on `GET`.

### 16.3 D-4F4-3 — no audit trail in 4F.4; **L-15 opened.** **APPROVED (a).**

4F.4 implements **no** audit trail for policy threshold changes.

| Row | Obligation | Why deferred | Owner | Settled by |
|---|---|---|---|---|
| **L-15** | **Administrative changes to `IdentityConfidencePolicy` are unaudited.** Creating, updating or deleting an identity-confidence threshold is a security-relevant administrative act, and nothing records who changed it, when, or from what to what | §5.2 fixes the minimum surface at *"create/read/update a policy … and nothing more"*. `action_execution_history` models the *action* lifecycle, not administrative mutation, so using it would need a schema decision outside this slice | **`action-engine`** | **4F closure**, or earlier if an audit design is separately ratified |

**Forbidden:** an Event Bus subject created merely to carry this audit gap;
closing L-15 later without evidence.

### 16.4 D-4F4-4 — no production threshold value. **APPROVED (a).**

**No production default threshold, and no seed.** A deployment that installs
nothing keeps the 1.0 fail-closed default at every risk tier.

4F.8's AC-8 run creates the LOW-risk policy it needs **through the production
API**, with a value ratified at that acceptance run.

**Test-only fixtures are permitted**, and **no fixture value may reach
production source or production initialization** — no default, no constant in
`src/` standing in for a chosen threshold, no migration insert.

### 16.5 The security ceiling, as implemented

The ratification requires that *"threshold values that violate the existing
security ceiling must be rejected"*. Implemented as: **a written threshold may
not exceed `0.75`**, the real achievable single-signal identity confidence.

**This removes no security capability, because strictness is expressed by
omission.** Stage 3 uses 1.0 for any risk tier absent from the map, so:

| Intent | How it is expressed |
|---|---|
| Maximum strictness for a tier | **Omit the tier.** Threshold stays 1.0 |
| Maximum strictness everywhere | **No policy row**, or `DELETE` |
| A deliberate, reachable relaxation | List the tier with a value `<= 0.75` |

So the rule reads: **you may only write a threshold you could actually
satisfy.** A value above `0.75` is unsatisfiable by any identity signal that
exists today, so accepting it would store a policy that looks configured and can
never pass — the failure mode the rule exists to prevent.

**ADR-004 is not violated to enforce it.** `action-engine` **does not import**
`perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING`; it declares its own
constant, and a drift guard in `tools/tests/` — which already scans the
repository for exactly this class of invariant — reads both as **source text**
rather than importing either.

**If fusion (L-11) ever raises achievable confidence above 0.75, this bound must
be revisited**, and the drift guard is what will force that conversation rather
than letting the two numbers silently diverge.

---

## 17. SLOC budget

**Current: 46,005 on the 4F scope. Headroom to the 50,000 hard gate: 3,995.**

Method, unchanged from 4E's Gate Review and now scripted: `cloc` v2.06
`--skip-uniqueness` over a pristine `git archive` export; scopes
`services/*/src` + `packages/*/src` + `services/*/alembic/versions` (Comparable),
plus `agent-os/*/src`, `agent-os/*/alembic/versions`, `agents` (Wider), plus
`apps/*/src` (Full), plus `companion/` less `companion/*/tests` (4F scope).
**Tests are outside every scope** (TDD 4F §17).

| | |
|---|---|
| TDD 4F §17's estimate for CF-9's write surface | **100–200** |
| Projected after 4F.4 | **~46,105–46,205** |
| Projected headroom | **~3,795–3,895** |

**The gate is not projected to be crossed by this slice**, and the slice is small
enough that it is not the one at risk. **F-2's open question** — whether
`companion/`'s `Cargo.toml`/`Dockerfile`/`README.md` belong in the count, a
142-line difference — **does not change that**, and remains **L-5's** to settle at
4F closure (TDD 4F.3 §17.1).

**Code is never moved or reduced to game the metric** (TDD 4F §17).

---

## 18. Implementation and closure sequence

1. **Ratify §15's four questions.** A-4F4-1, A-4F4-2 and A-4F4-3 change what is
   built; A-4F4-4 changes what may be written into `src/`.
2. Create `phase-4f.4` from the then-current base. **It does not exist yet and
   must not be created before ratification.**
3. Implement deliverables 1–5. Stage 3 is not touched.
4. Verify locally: full suite, lint, mypy, import-linter, codegen drift, SLOC.
5. Real-infra evidence for W-1, W-2, W-3, W-8 against real Postgres.
6. Open a PR **only if the user asks**, to obtain exact-SHA CI evidence
   (protocol §11.1).
7. Produce the **4F.4 slice completion record with a deferred-obligations
   ledger** — protocol §0.1 and §0.2. **Not a Gate Review**: category 3 is
   deferred, and 4F's Gate Review is 4F.8's.
8. **Record CF-9 as still OPEN**, with §13.3's condition-by-condition status.

**Phase 4F is not complete at the end of 4F.4.** 4F.5 through 4F.8 remain.
