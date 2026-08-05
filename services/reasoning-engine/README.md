# reasoning-engine

The Reasoning Engine (Bible Part 8) is NOVA's cognitive bridge: it transforms
information from Long-Term Memory, the Knowledge Engine, the World Model,
Personal Context, Current Goals, and Available Capabilities into decisions.
It owns no system of record for any of those six inputs -- it owns only
records of its own reasoning processes (ADR-026). See
`docs/design/phase-2b/00-reasoning-engine.md` for the full Technical Design
Document.

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
uv run --package reasoning-engine pytest services/reasoning-engine/tests
```
