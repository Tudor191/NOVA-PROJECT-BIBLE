# autonomy-engine

TODO: one paragraph describing this engine's responsibility, and which Bible Part
(docs/bible/) it implements.

*(Replaced 2026-10-16, ledger row L-19. The scaffold's `TODO` above is
preserved per protocol §0.3.4; the paragraph below is the description.)*

**`autonomy-engine` decides whether NOVA may act at all** -- Bible Part 14,
*Autonomy*. It owns the Autonomy Level (0-5 named; 0-2 defined and
selectable, 3-5 refused), the Policy Engine (`deny`, `require_approval`,
`auto_execute`; there is no `allow`), the ten-category Permission Matrix, the
Trust Engine's score, the suggestion inbox and an append-only decision log
(TDD 4D; TDD 4F.5 for Level 2). It executes nothing itself: at Level 2 a
low-risk action permitted by an `auto_execute` policy is dispatched to
`action-engine` over `action.execute`, whose own fail-closed gates still
apply; at Level 1 or below every proposal waits for the user. The trust
input from `digital-twin-engine` does not exist yet (CF-10), so trust can
never refuse a decision -- `domain/decision.py`'s `_trust_denies` documents
that seam.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Request (publish allow-list) | `action.execute`: request/reply to `action-engine`, Level 2 only (4F.5) | `ActionExecuteRequestPayload` → `ActionResultPayload` |
| Serve (subscribe allow-list) | `autonomy.decision.requested`: **internal** request/reply from `cognitive-state-engine`; this engine is its only consumer (4F.6) | `AutonomyDecisionRequestedPayload` → `AutonomyDecisionReplyPayload` (reply not a registered subject) |

*(Until 4F.6 this table held the scaffold's single placeholder row, "TODO |
TODO | TODO". Preserved per protocol §0.3.4. The rest of this README is still
the scaffold, and that gap is recorded in the 4F.6 completion record's ledger.)*

*(4F.P, 2026-10-05; TDD 4F.P §30.2. The subjects above are unchanged, and the
scaffold gap is still open.)*

- **The trigger carries the authored pair.** `AutonomyDecisionRequestedPayload`
  now carries `operation` and `parameters`, and `action.execute`'s
  `parameters` is `{"operation": operation, **parameters}` (A-4FP-6). If either
  one is absent, the decision stays a suggestion.
- **The outcome follows `action-engine`'s reply.** For a Level-2 dispatch, the
  recorded outcome is the one the reply maps to, through
  `ACTION_STATUS_OUTCOMES` in `domain/decision.py` (A-4FP-7):
  - `completed` → `execute`, and nothing else records `execute`;
  - `denied` → `propose`;
  - every other status → the new `execution_failed`.

Neither subject is in `ws-gateway`'s `PUBLIC_TOPICS`, and neither is exposed
through a gateway. The trigger's handler is `decision_orchestration.py`, the
first production caller of `decide()`.

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

*(Added 2026-10-16, ledger row L-19. The three routes above were the whole
list; this engine has served the `/v1/autonomy` surface since Phase 4D. All
of it is reachable from the browser through `api-gateway`'s `/v1/autonomy`
prefix, with a session. Identity is resolved server-side: no route takes a
`user_id`.)*

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/autonomy` | Overview: level, policies, permission matrix, trust |
| `GET` | `/v1/autonomy/level` | The configured level and every level's selectability |
| `PUT` | `/v1/autonomy/level` | Set Levels 0-2; 3-5 are a 422 naming the reason |
| `GET` | `/v1/autonomy/policies` | List policies |
| `POST` | `/v1/autonomy/policies` | Create a policy |
| `PATCH` | `/v1/autonomy/policies/{policy_id}` | Update fields, including `enabled` |
| `DELETE` | `/v1/autonomy/policies/{policy_id}` | Delete a policy |
| `GET` | `/v1/autonomy/permissions` | The ten-category matrix |
| `PUT` | `/v1/autonomy/permissions` | Upsert only the categories named |
| `GET` | `/v1/autonomy/suggestions` | Keyset-paginated inbox with each suggestion's gate report |
| `POST` | `/v1/autonomy/suggestions/{suggestion_id}/decide` | Approve or reject; executes nothing |

There is deliberately no route that creates a suggestion (TDD 4D §8.1).

## Internal structure

*(Added 2026-10-16, SAD 15 §9.1 item 3. Drawn from `src/` at this commit.)*

```
src/nova_autonomy_engine/
├── main.py                       create_app(): bus, repository, trust source,
│                                 dispatcher, serve(autonomy.decision.requested)
├── config.py                     Settings (primary_user_id, timeouts, DSN)
├── observability.py              AutonomyMetrics: the three instruments below
├── decision_orchestration.py     the trigger's consumer; the production caller of decide()
├── api/
│   ├── autonomy.py               /v1/autonomy/* (table above)
│   ├── schemas.py                request/response models
│   └── health.py                 /internal/health, /internal/readiness
├── clients/
│   ├── action_dispatch.py        ActionDispatchClient: action.execute, 15 s bound
│   └── conversational_trust.py   the CF-10 seam: reports UNAVAILABLE
├── domain/                       no I/O
│   ├── decision.py               decide(): Level ▸ Policy ▸ Permission ▸ Trust ▸ dispatch
│   ├── levels.py                 parse_level, require_selectable
│   ├── models.py                 AutonomyLevel, Policy, PermissionGrant, DecisionOutcome, ...
│   ├── permissions.py            the ten-category matrix
│   ├── policy.py                 evaluate_policies (deny wins; auto_execute narrowed)
│   ├── ports.py                  AutonomyRepository, ActionDispatchPort, trust source
│   ├── risk.py                   risk ordering
│   └── trust.py                  compute_trust_score
├── events/                       published.py / subscribed.py allow-lists
├── models/                       scaffold package; empty
└── repository/
    ├── postgres_autonomy_repository.py
    ├── models.py                 ORM: autonomy_level, policy, permission_grant,
    │                             suggestion, decision_log
    └── cursor.py                 keyset cursors
```

Shared packages: `nova-contracts`, `nova-eventbus-sdk`, `nova-service-kit`
(database engine and sessions), `nova-observability`.

## Observability

*(Added 2026-10-16, SAD 15 §9.1 items 9 and 10.)*

| Metric | Type | Labels |
|---|---|---|
| `autonomy_decisions_total` | counter | `source` (`trigger`, `suggestion_inbox`), `outcome` (every `DecisionOutcome`, plus `rejected` and `degraded`) |
| `autonomy_decision_duration_seconds` | histogram (seconds, to 30 s) | `outcome` |
| `autonomy_configuration_changes_total` | counter | `kind` (`level`, `policy`, `permissions`), `operation` |

| Log message | When |
|---|---|
| `autonomy configuration changed` | Every level, policy or permission change, with the values **before and after** |
| `suggestion decision` | Every inbox decision attempt and its result, including refusals |
| `autonomy decision recorded` | A triggered decision, with `event_id`, `correlation_id`, `subject_id`, `outcome` |
| `autonomy.decision.requested rejected/degraded ...` | The trigger's refusal and degraded paths (existing) |

**The configuration log is not an audit trail.** Nothing is persisted, and
the actor is not recorded beyond ADR-025's single trusted user. A persisted
audit of these changes is an open decision (Phase 4 closure matrix, N-02).
**Traces are not built** here or anywhere in the repository.

## Testing

```bash
uv run --package autonomy-engine pytest services/autonomy-engine/tests -m "not real_infra"
uv run --package autonomy-engine pytest services/autonomy-engine/tests -m real_infra  # Postgres + NATS
```
