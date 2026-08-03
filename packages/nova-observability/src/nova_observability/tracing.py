"""OpenTelemetry tracing setup, shared across every engine.

Exports spans via OTLP/HTTP to the endpoint configured by the standard
`OTEL_EXPORTER_OTLP_ENDPOINT` environment variable, defaulting to the local
otel-collector service started by infra/docker/docker-compose.local.yml.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

_configured = False


def configure_tracing(service_name: str) -> None:
    """Configure the global TracerProvider for `service_name`. Safe to call more than once."""
    global _configured
    if _configured:
        return
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)
