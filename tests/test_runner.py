"""Unit tests for the evaluation runner, caching, rate limiting, and resumption.

Verifies:
- run_evaluation executes hermetically with fake adapters.
- SQLite cache and results.jsonl enable seamless resumption without duplicate calls.
- Rate-limiting interval throttling functions accurately.
- Consecutive rate-limit failures trigger an abort with clear error context.
- Incremental results writing ensures no data loss upon interruption.
"""

import time
from pathlib import Path
from typing import Any

import pytest

from sanket.evaluate.adapters.base import BaseAdapter
from sanket.evaluate.adapters.fake import OracleAdapter, RandomAdapter
from sanket.evaluate.cache import ResponseCache
from sanket.evaluate.runner import run_evaluation
from sanket.schema import (
    ANSWER_OPTIONS,
    Answer,
    RawResponse,
    Receipt,
    Task,
)


def _make_test_task(task_id: str, gold: Answer = "AHEAD") -> Task:
    """Helper creating a minimal valid Task instance."""
    receipt = Receipt(
        solver_answer=gold,
        independent_answer=gold,
        agree=True,
        fidelity_ok=True,
        visibility_ok=True,
        evidence_visible_ratio=1.0,
    )
    return Task(
        task_id=task_id,
        schema_version="1.0.0",
        generator_version="1.0.0",
        seed=100,
        qtype="DIRECT",
        question=f"Which way for {task_id}?",
        options=list(ANSWER_OPTIONS),
        gold=gold,
        image_path=f"/fake/{task_id}.png",
        scene_path=f"/fake/{task_id}.json",
        target_dest_id=f"dest_{task_id}",
        turn_cw=None,
        receipt=receipt,
    )


class CallTrackingSpyAdapter(BaseAdapter):
    """Adapter that counts calls to verify caching and resumption behavior."""

    def __init__(self, name: str = "spy", rpm: int = 0) -> None:
        super().__init__(name=name, model_id=f"spy-model-{name}", rpm=rpm)
        self.call_count = 0

    def answer(
        self,
        task: Task,
        mode: str = "image",
        prompt_version: str = "v1",
        **kwargs: Any,
    ) -> RawResponse:
        self.call_count += 1
        return RawResponse(
            text=f"ANSWER: {task.gold}",
            latency_s=0.001,
            meta={"call_count": self.call_count},
        )


class FlakyRateLimitAdapter(BaseAdapter):
    """Adapter that persistently simulates HTTP 429 rate limit errors."""

    def __init__(self, name: str = "flaky") -> None:
        super().__init__(name=name, model_id="flaky-model", rpm=0)
        self.attempts = 0

    def answer(
        self,
        task: Task,
        mode: str = "image",
        prompt_version: str = "v1",
        **kwargs: Any,
    ) -> RawResponse:
        self.attempts += 1
        raise RuntimeError("HTTP 429: Too Many Requests - Resource Exhausted")


def test_runner_basic_execution(tmp_path: Path) -> None:
    """Verify that run_evaluation runs on tasks and writes cache and results.jsonl."""
    tasks = [_make_test_task(f"t_{i}", gold="AHEAD") for i in range(3)]
    results_file = tmp_path / "results.jsonl"
    cache_db = tmp_path / "cache.db"
    cache = ResponseCache(cache_db)

    adapter = OracleAdapter()
    results, metrics = run_evaluation(
        tasks=tasks,
        models=[adapter],
        modes=["image"],
        cache=cache,
        results_file=results_file,
        show_progress=False,
    )

    # 3 tasks x 1 mode x 1 model = 3 results
    assert len(results) == 3
    assert all(r.correct for r in results)
    assert metrics["total"] == 3
    assert metrics["accuracy"] == 1.0

    # Verify results.jsonl file
    assert results_file.exists()
    lines = [
        line.strip()
        for line in results_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 3

    # Verify SQLite cache
    for task in tasks:
        cached = cache.get(adapter.model_id, task.task_id, "image", "v1")
        assert cached is not None
        assert "ANSWER: AHEAD" in cached.text


def test_runner_resumption_skips_processed_tasks(tmp_path: Path) -> None:
    """Verify that runner does not re-query tasks that already exist in results.jsonl or cache."""
    tasks_phase1 = [_make_test_task(f"task_{i}") for i in range(3)]
    tasks_phase2 = [_make_test_task(f"task_{i}") for i in range(5)]

    results_file = tmp_path / "results.jsonl"
    cache_db = tmp_path / "cache.db"
    cache = ResponseCache(cache_db)
    spy_adapter = CallTrackingSpyAdapter(name="spy1")

    # Run 1: 3 tasks
    res1, _ = run_evaluation(
        tasks=tasks_phase1,
        models=[spy_adapter],
        modes=["image"],
        cache=cache,
        results_file=results_file,
        show_progress=False,
    )
    assert len(res1) == 3
    assert spy_adapter.call_count == 3

    # Run 2: 5 tasks (3 already in results_file, 2 new)
    res2, _ = run_evaluation(
        tasks=tasks_phase2,
        models=[spy_adapter],
        modes=["image"],
        cache=cache,
        results_file=results_file,
        show_progress=False,
    )
    assert len(res2) == 5
    # The adapter should ONLY have been called for the 2 new tasks
    assert spy_adapter.call_count == 5

    # Run 3: Same 5 tasks with fresh empty results_file but existing cache
    fresh_results_file = tmp_path / "fresh_results.jsonl"
    res3, _ = run_evaluation(
        tasks=tasks_phase2,
        models=[spy_adapter],
        modes=["image"],
        cache=cache,
        results_file=fresh_results_file,
        show_progress=False,
    )
    assert len(res3) == 5
    # Should hit SQLite cache for all 5 tasks -> zero additional adapter calls!
    assert spy_adapter.call_count == 5


def test_runner_rate_limit_throttle(tmp_path: Path) -> None:
    """Verify that rate limiter sleeps between queries when rpm is specified."""
    # 300 RPM = 0.2s interval
    throttle_adapter = CallTrackingSpyAdapter(name="throttled", rpm=300)
    tasks = [_make_test_task(f"task_rpm_{i}") for i in range(3)]
    results_file = tmp_path / "rpm_results.jsonl"
    cache = ResponseCache(tmp_path / "rpm_cache.db")

    start_time = time.time()
    run_evaluation(
        tasks=tasks,
        models=[throttle_adapter],
        modes=["image"],
        cache=cache,
        results_file=results_file,
        show_progress=False,
    )
    elapsed = time.time() - start_time

    # 3 calls at 0.2s interval between calls -> at least ~0.35s total
    assert elapsed >= 0.30


def test_runner_aborts_on_consecutive_rate_limits(tmp_path: Path) -> None:
    """Verify that runner halts with RuntimeError after N consecutive rate limit failures."""
    flaky = FlakyRateLimitAdapter()
    tasks = [_make_test_task(f"task_fail_{i}") for i in range(5)]
    results_file = tmp_path / "fail_results.jsonl"
    cache = ResponseCache(tmp_path / "fail_cache.db")

    with pytest.raises(RuntimeError, match="consecutive rate-limit failures"):
        run_evaluation(
            tasks=tasks,
            models=[flaky],
            modes=["image"],
            cache=cache,
            results_file=results_file,
            max_consecutive_rate_limits=2,
            max_retries=1,
            retry_min_wait=0.001,
            show_progress=False,
        )


def test_runner_random_adapter(tmp_path: Path) -> None:
    """Verify evaluation with RandomAdapter runs cleanly and yields structured metrics."""
    random_adapter = RandomAdapter(seed=999)
    tasks = [_make_test_task(f"task_rnd_{i}", gold="RIGHT") for i in range(10)]
    results_file = tmp_path / "rnd_results.jsonl"
    cache = ResponseCache(tmp_path / "rnd_cache.db")

    results, metrics = run_evaluation(
        tasks=tasks,
        models=[random_adapter],
        modes=["image"],
        cache=cache,
        results_file=results_file,
        show_progress=False,
    )

    assert len(results) == 10
    assert metrics["total"] == 10
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert "wilson_95" in metrics
