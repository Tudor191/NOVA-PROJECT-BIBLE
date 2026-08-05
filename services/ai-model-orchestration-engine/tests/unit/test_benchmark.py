from nova_ai_model_orchestration_engine.connectors.fake_connector import FakeConnector
from nova_ai_model_orchestration_engine.domain.benchmark import BENCHMARK_PROMPTS, run_benchmark


async def test_run_benchmark_against_working_connector() -> None:
    connector = FakeConnector(response_text="hello there")
    result = await run_benchmark(connector)
    assert result.success_rate == 1.0
    assert result.avg_latency_ms >= 0.0
    assert result.avg_quality_score == 1.0


async def test_run_benchmark_against_failing_connector() -> None:
    connector = FakeConnector(should_fail=True)
    result = await run_benchmark(connector)
    assert result.success_rate == 0.0
    assert result.avg_latency_ms == 0.0
    assert result.avg_quality_score == 0.0


async def test_run_benchmark_calls_connector_once_per_prompt() -> None:
    connector = FakeConnector()
    await run_benchmark(connector)
    assert connector.calls == len(BENCHMARK_PROMPTS)
