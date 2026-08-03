# nova-observability

Shared OpenTelemetry (traces + metrics) and structured JSON logging setup, used
identically by every engine (docs/architecture/01-technology-stack.md §7).

```python
from nova_observability import configure_observability, get_logger, get_tracer

configure_observability("memory-engine")  # call once at process startup

logger = get_logger(__name__)
tracer = get_tracer(__name__)

with tracer.start_as_current_span("retrieve-memories"):
    logger.info("retrieving memories", extra={"correlation_id": str(correlation_id)})
```

- **Traces** export via OTLP/HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` (defaults to the
  local `otel-collector` service in `infra/docker/docker-compose.local.yml`), which
  forwards them to Tempo.
- **Metrics** are Prometheus-pull, not push: `prometheus_asgi_app()` exposes
  `/internal/metrics` (mounted by every engine, docs/architecture/11 §3), and
  Prometheus scrapes each engine directly -- no collector round-trip.
- **Logs** are JSON on stdout; shipping them into Loki (Promtail or the Docker Loki
  logging driver) is Compose-level configuration, not application code.
