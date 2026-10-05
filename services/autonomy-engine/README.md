# autonomy-engine

TODO: one paragraph describing this engine's responsibility, and which Bible Part
(docs/bible/) it implements.

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

## Testing

```bash
uv run --package autonomy-engine pytest services/autonomy-engine/tests
```
