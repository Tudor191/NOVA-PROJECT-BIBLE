# agent-os/supervisors

TODO: one paragraph describing this NAOS component's responsibility
(docs/architecture/12-agent-architecture.md).

Not an instance of the standard `-engine` template
(docs/architecture/02-repository-and-folder-structure.md:53-65) -- no
`/v1/...` REST surface; `/internal/health`/`/internal/readiness` come from
`nova-service-kit`'s `make_health_router()` (unmodified reuse), `/internal/
metrics` from `nova-observability`'s `prometheus_asgi_app()`.

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
uv run --package supervisors pytest agent-os/supervisors/tests
```
