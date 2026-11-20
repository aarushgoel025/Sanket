"""Unit tests for exact-match scorer, metrics calculation, and fake adapters.

Verifies:
- OracleAdapter achieves 100% accuracy.
- RandomAdapter scores near 10% on 400 tasks across the 10 answer options.
- AlwaysAdapter('AHEAD') exhibits expected bias (100% on AHEAD, 0% on others).
- Wilson 95% confidence intervals are mathematically sound.
"""

import pytest

from sanket.evaluate.adapters.fake import AlwaysAdapter, OracleAdapter, RandomAdapter
from sanket.evaluate.parser import parse_answer
from sanket.evaluate.scorer import compute_metrics, score_single, wilson_score_interval
from sanket.schema import (
    ANSWER_OPTIONS,
    Answer,
    EvaluationResult,
    Receipt,
    Task,
)


def create_mock_task(
    task_id: str,
    qtype: str,
    gold: Answer,
    seed: int = 42,
    pair_id: str | None = None,
    pair_role: str | None = None,
) -> Task:
    """Construct a minimal valid Task instance for hermetic evaluation tests."""
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
        seed=seed,
        qtype=qtype,  # type: ignore[arg-type]
        question=f"Which way to destination for {task_id}?",
        options=list(ANSWER_OPTIONS),
        gold=gold,
        image_path=f"/fake/images/{task_id}.png",
        scene_path=f"/fake/scenes/{task_id}.json",
        target_dest_id=f"dest_{task_id}",
        turn_cw=None,
        pair_id=pair_id,
        pair_role=pair_role,  # type: ignore[arg-type]
        receipt=receipt,
    )


@pytest.fixture
def dataset_400_tasks() -> list[Task]:
    """Generate 400 balanced tasks across question types and gold answer options."""
    directional_qtypes = ["DIRECT", "BINDING", "OVERRIDE", "EGOCENTRIC"]
    tasks: list[Task] = []
    for i in range(400):
        gold = ANSWER_OPTIONS[i % len(ANSWER_OPTIONS)]
        if gold == "CLOSED":
            qtype = "CLOSURE"
        elif gold == "NOT_INDICATED":
            qtype = "ABSENT"
        else:
            qtype = directional_qtypes[i % len(directional_qtypes)]

        pair_id = f"pair_{i // 2}" if i < 100 else None
        pair_role = "a" if i < 50 else ("b" if i < 100 else None)

        tasks.append(
            create_mock_task(
                task_id=f"task_{i:04d}",
                qtype=qtype,
                gold=gold,
                seed=1000 + i,
                pair_id=pair_id,
                pair_role=pair_role,
            )
        )
    return tasks


def test_oracle_adapter_scores_100_percent(dataset_400_tasks: list[Task]) -> None:
    """OracleAdapter must achieve exactly 100% accuracy on all 400 tasks."""
    adapter = OracleAdapter()
    results: list[EvaluationResult] = []

    for task in dataset_400_tasks:
        raw = adapter.answer(task, mode="image")
        parsed = parse_answer(raw.text)
        correct = score_single(task, parsed)
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id=adapter.model_id,
                mode="image",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=raw.text,
                latency_s=raw.latency_s,
                timestamp=0.0,
                qtype=task.qtype,
                pair_id=task.pair_id,
                pair_role=task.pair_role,
            )
        )

    metrics = compute_metrics(results)
    assert metrics["total"] == 400
    assert metrics["correct"] == 400
    assert metrics["accuracy"] == 1.0
    assert metrics["wilson_95"] == (0.9905, 1.0)
    assert metrics["unparseable"] == 0
    assert metrics["pair_consistency"] == 1.0


def test_random_adapter_scores_near_10_percent(dataset_400_tasks: list[Task]) -> None:
    """RandomAdapter across 10 options must score near 10% on 400 balanced tasks."""
    adapter = RandomAdapter(seed=42)
    results: list[EvaluationResult] = []

    for task in dataset_400_tasks:
        raw = adapter.answer(task, mode="image")
        parsed = parse_answer(raw.text)
        correct = score_single(task, parsed)
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id=adapter.model_id,
                mode="image",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=raw.text,
                latency_s=raw.latency_s,
                timestamp=0.0,
                qtype=task.qtype,
                pair_id=task.pair_id,
                pair_role=task.pair_role,
            )
        )

    metrics = compute_metrics(results)
    assert metrics["total"] == 400
    # Expected: ~10% (40 correct). Check within reasonable statistical band: 6% to 15%
    assert 0.06 <= metrics["accuracy"] <= 0.15, (
        f"Random accuracy was {metrics['accuracy']}, expected ~0.10"
    )
    ci_low, ci_high = metrics["wilson_95"]
    assert ci_low <= metrics["accuracy"] <= ci_high


def test_always_adapter_shows_type_bias(dataset_400_tasks: list[Task]) -> None:
    """AlwaysAdapter('AHEAD') must score 100% on AHEAD tasks, and 0% on CLOSURE and ABSENT."""
    adapter = AlwaysAdapter(option="AHEAD")
    results: list[EvaluationResult] = []

    for task in dataset_400_tasks:
        raw = adapter.answer(task, mode="image")
        parsed = parse_answer(raw.text)
        correct = score_single(task, parsed)
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id=adapter.model_id,
                mode="image",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=raw.text,
                latency_s=raw.latency_s,
                timestamp=0.0,
                qtype=task.qtype,
                pair_id=task.pair_id,
                pair_role=task.pair_role,
            )
        )

    metrics = compute_metrics(results)

    # CLOSURE gold is CLOSED, so Always('AHEAD') must get 0%
    assert metrics["by_qtype"]["CLOSURE"]["accuracy"] == 0.0
    # ABSENT gold is NOT_INDICATED, so Always('AHEAD') must get 0%
    assert metrics["by_qtype"]["ABSENT"]["accuracy"] == 0.0
    # Overall hallucination rate should be 100% since ABSENT tasks got a direction ('AHEAD')
    assert metrics["hallucination_rate"] == 1.0

    # For tasks where gold actually is AHEAD:
    ahead_results = [r for r in results if r.gold == "AHEAD"]
    assert len(ahead_results) == 40
    assert all(r.correct for r in ahead_results)


def test_oracle_text_mode_scores_100_percent(dataset_400_tasks: list[Task]) -> None:
    """OracleAdapter must achieve exactly 100% accuracy in text mode as well."""
    adapter = OracleAdapter()
    results: list[EvaluationResult] = []

    for task in dataset_400_tasks[:50]:
        raw = adapter.answer(task, mode="text")
        parsed = parse_answer(raw.text)
        correct = score_single(task, parsed)
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id=adapter.model_id,
                mode="text",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=raw.text,
                latency_s=raw.latency_s,
                timestamp=0.0,
                qtype=task.qtype,
            )
        )

    metrics = compute_metrics(results)
    assert metrics["total"] == 50
    assert metrics["correct"] == 50
    assert metrics["accuracy"] == 1.0


def test_unparseable_responses_scored_zero(dataset_400_tasks: list[Task]) -> None:
    """Unparseable responses must be scored False and logged in metrics."""
    results: list[EvaluationResult] = []
    unparseable_text = "I don't know the answer to this question."

    for task in dataset_400_tasks[:20]:
        parsed = parse_answer(unparseable_text)
        assert parsed is None
        correct = score_single(task, parsed)
        assert correct is False
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id="unparseable_bot",
                mode="image",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=unparseable_text,
                latency_s=0.01,
                timestamp=0.0,
                qtype=task.qtype,
            )
        )

    metrics = compute_metrics(results)
    assert metrics["total"] == 20
    assert metrics["correct"] == 0
    assert metrics["accuracy"] == 0.0
    assert metrics["unparseable"] == 20


def test_always_adapter_closed_choice(dataset_400_tasks: list[Task]) -> None:
    """AlwaysAdapter('CLOSED') must score 100% on CLOSURE and 0% on directional tasks."""
    adapter = AlwaysAdapter(option="CLOSED")
    results: list[EvaluationResult] = []

    for task in dataset_400_tasks:
        raw = adapter.answer(task, mode="image")
        parsed = parse_answer(raw.text)
        correct = score_single(task, parsed)
        results.append(
            EvaluationResult(
                task_id=task.task_id,
                model_id=adapter.model_id,
                mode="image",
                prompt_version="v1",
                gold=task.gold,
                parsed_answer=parsed,
                correct=correct,
                raw_text=raw.text,
                latency_s=raw.latency_s,
                timestamp=0.0,
                qtype=task.qtype,
            )
        )

    metrics = compute_metrics(results)
    assert metrics["by_qtype"]["CLOSURE"]["accuracy"] == 1.0
    assert metrics["by_qtype"]["DIRECT"]["accuracy"] == 0.0


def test_wilson_confidence_interval_bounds() -> None:
    """Test mathematical boundary properties of the Wilson score interval."""
    # Zero trials
    assert wilson_score_interval(0, 0) == (0.0, 0.0)

    # 100% successes on 100 trials
    ci_100 = wilson_score_interval(100, 100)
    assert ci_100[0] > 0.95 and ci_100[1] == 1.0

    # 0% successes on 100 trials
    ci_0 = wilson_score_interval(0, 100)
    assert ci_0[0] == 0.0 and ci_0[1] < 0.05

    # 50% on 100 trials (centered near 0.50)
    ci_50 = wilson_score_interval(50, 100)
    assert ci_50[0] < 0.50 < ci_50[1]
    assert round(ci_50[0] + ci_50[1], 1) == 1.0
