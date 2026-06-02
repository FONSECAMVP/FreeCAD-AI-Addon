"""
Non-functional requirement tests — REQ-NFR-001, REQ-NFR-002.

REQ-NFR-001 (latency ≤5s, non-blocking): the non-blocking property is
structural — LLMWorker runs in QThread, never calls FreeCAD API from
the worker thread. Verified by test_worker_logic.py. Latency against a
real endpoint requires manual validation with a local Ollama instance.

REQ-NFR-002 (tool execution ≤2s): verified here via timed dispatch calls
against the mock FreeCAD API. Catches accidental blocking in executor path.
"""

import time

import pytest


@pytest.fixture()
def _bench_executor(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "bench_tool",
            "description": "Benchmark tool",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "number", "description": "value"}},
                "required": ["x"],
            },
        },
    }
    registry.register("bench_tool", schema, lambda a: {"ok": True}, workbench="Part")
    return ToolExecutor(registry)


@pytest.mark.fast
def test_executor_dispatch_under_2s(_bench_executor):
    """REQ-NFR-002: single tool dispatch must complete in < 2s (mock FreeCAD API)."""
    times = []
    for _ in range(50):
        start = time.perf_counter()
        _bench_executor.dispatch("bench_tool", {"x": 1.0})
        times.append(time.perf_counter() - start)

    worst = max(times)
    assert worst < 2.0, f"Slowest dispatch {worst:.4f}s exceeded 2s limit (REQ-NFR-002)"


@pytest.mark.fast
def test_executor_dispatch_p99_under_100ms(_bench_executor):
    """Regression guard: p99 dispatch latency must stay under 100ms (mock path)."""
    times = []
    for _ in range(100):
        start = time.perf_counter()
        _bench_executor.dispatch("bench_tool", {"x": 1.0})
        times.append(time.perf_counter() - start)

    times.sort()
    p99 = times[98]
    assert p99 < 0.1, f"p99 dispatch {p99*1000:.1f}ms exceeded 100ms regression threshold"


@pytest.mark.fast
def test_nfr001_non_blocking_property_documented():
    """
    REQ-NFR-001 structural check: LLMWorker must be a QThread subclass,
    guaranteeing LLM HTTP calls never block the Qt event loop.

    The latency criterion (≤5s to first token on 100Mbps) requires a real
    LLM endpoint and is validated manually with a local Ollama instance.
    """
    from freecad_ai.worker import LLMWorker

    if LLMWorker is None:
        pytest.skip("Qt not available in test environment — LLMWorker not instantiated")

    try:
        from PySide2.QtCore import QThread

        assert issubclass(LLMWorker, QThread), "LLMWorker must subclass QThread (REQ-NFR-001)"
    except ImportError:
        try:
            from PySide6.QtCore import QThread

            assert issubclass(LLMWorker, QThread), "LLMWorker must subclass QThread (REQ-NFR-001)"
        except ImportError:
            pytest.skip("Qt not available — structural check skipped")
