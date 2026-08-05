"""Bible Part 7 "Model Benchmarking" (design doc §2): a small, fixed evaluation
set run against a connector, scored structurally -- average `structural_confidence`
and success rate across the set, never semantic correctness (§7's "Validate
Output" boundary: judging whether an answer is *right* is a Reasoning Engine
concern, Phase 2B, outside this engine's scope). This keeps `avg_quality_score`
an honest, structural signal ("did this model respond coherently under a fixed
workload"), not a claim of intelligence measurement this engine has no way to
make -- the same honesty precedent as `router.py`'s complexity heuristic.
"""

from __future__ import annotations

import time

from nova_ai_model_orchestration_engine.domain.models import ContextComponent, GenerateRequest
from nova_ai_model_orchestration_engine.domain.ports import ModelConnector

__all__ = ["BENCHMARK_PROMPTS", "BenchmarkResult", "run_benchmark"]

BENCHMARK_PROMPTS: tuple[str, ...] = (
    "Say hello in one short sentence.",
    "What is 2 + 2?",
    "Name one color.",
)
"""A small, fixed evaluation set -- deliberately trivial: this measures "does
this connector respond coherently at all," not domain expertise."""


class BenchmarkResult:
    __slots__ = ("avg_latency_ms", "avg_quality_score", "success_rate")

    def __init__(
        self, *, avg_latency_ms: float, avg_quality_score: float, success_rate: float
    ) -> None:
        self.avg_latency_ms = avg_latency_ms
        self.avg_quality_score = avg_quality_score
        self.success_rate = success_rate


async def run_benchmark(connector: ModelConnector) -> BenchmarkResult:
    """Impure: calls `connector.generate()` once per `BENCHMARK_PROMPTS` entry.
    A prompt that raises simply doesn't count toward `avg_latency_ms`/
    `avg_quality_score` -- a connector that fails every prompt returns a
    `success_rate` of `0.0`, not an exception (§2: this feeds back into
    `capability_matrix.py`, which expects a score, not a failure to score)."""
    latencies: list[float] = []
    confidences: list[float] = []
    successes = 0
    for prompt in BENCHMARK_PROMPTS:
        request = GenerateRequest(
            context=[
                ContextComponent(
                    source="user_request", text=prompt, token_estimate=max(1, len(prompt) // 4)
                )
            ],
            requesting_engine="ai-model-orchestration-engine.benchmark_worker",
        )
        start = time.perf_counter()
        try:
            result = await connector.generate(request)
        except Exception:  # noqa: BLE001 -- a failing prompt just doesn't count as a success
            continue
        latencies.append((time.perf_counter() - start) * 1000)
        confidences.append(result.structural_confidence if result.text.strip() else 0.0)
        successes += 1

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    avg_quality = sum(confidences) / len(confidences) if confidences else 0.0
    return BenchmarkResult(
        avg_latency_ms=avg_latency,
        avg_quality_score=avg_quality,
        success_rate=successes / len(BENCHMARK_PROMPTS),
    )
