"""Guard: Prometheus scrapes every HTTP service the local stack runs.

`infra/observability/prometheus.yml` is a hand-maintained target list, and
`infra/docker/README.md` step 3 says each new engine adds itself to it. Until
2026-10-16 none ever had: the file scraped `nova-core` alone, so every other
engine's `/internal/metrics` existed and nothing read it (closure-matrix row
X-06, alias F-4F7-7). A metric nobody scrapes is not observability.

**Which services count.** Every compose service built from a `services/*` or
`agent-os/*` Dockerfile that runs the image's own command, the HTTP server.
The `*-worker` services override `command` with `arq` and serve no HTTP, so
they have nothing to scrape. Both directions are checked: a missing target
and a stale one.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.local.yml"
PROMETHEUS = REPO_ROOT / "infra" / "observability" / "prometheus.yml"
METRICS_PATH = "/internal/metrics"


def _http_services() -> set[str]:
    services = yaml.safe_load(COMPOSE.read_text())["services"]
    found = set()
    for name, cfg in services.items():
        build = cfg.get("build")
        dockerfile = build.get("dockerfile", "") if isinstance(build, dict) else ""
        if not dockerfile.startswith(("services/", "agent-os/")):
            continue
        if cfg.get("command"):  # a worker: arq, no HTTP server
            continue
        found.add(name)
    return found


def _scraped() -> dict[str, str]:
    """`host` -> the metrics path Prometheus requests from it."""
    config = yaml.safe_load(PROMETHEUS.read_text())
    targets = {}
    for job in config["scrape_configs"]:
        path = job.get("metrics_path", "/metrics")
        for static in job.get("static_configs", []):
            for target in static["targets"]:
                host, _, port = target.partition(":")
                assert port == "8000", f"{target}: every service listens on 8000 in-container"
                targets[host] = path
    return targets


def test_the_parsers_found_a_real_stack() -> None:
    # Anti-decoration control: two empty sets would compare equal.
    services = _http_services()
    assert len(services) >= 15
    assert {"nova-core", "api-gateway", "autonomy-engine"} <= services


def test_every_http_service_is_scraped() -> None:
    missing = _http_services() - set(_scraped())
    assert not missing, f"add these to {PROMETHEUS.name}: {sorted(missing)}"


def test_no_target_names_a_service_the_stack_does_not_run() -> None:
    stale = set(_scraped()) - _http_services()
    assert not stale, f"remove these from {PROMETHEUS.name}: {sorted(stale)}"


def test_every_target_is_scraped_at_the_internal_metrics_route() -> None:
    wrong = {host: path for host, path in _scraped().items() if path != METRICS_PATH}
    assert not wrong, f"doc 11 §3 mounts metrics at {METRICS_PATH}: {wrong}"
