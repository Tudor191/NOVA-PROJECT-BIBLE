# executive-cognition-engine

TODO: one paragraph describing this engine's responsibility, and which Bible Part
(docs/bible/) it implements.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| TODO | TODO | TODO |

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

## Testing

```bash
uv run --package executive-cognition-engine pytest services/executive-cognition-engine/tests
```
