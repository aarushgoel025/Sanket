"""Deterministic exact-match scorer and metrics calculator for model evaluations.

Compares parsed model answers against gold ground-truth labels.
No LLM judges used; strictly rule-based evaluation with Wilson 95% intervals.
"""

import math
from collections import defaultdict
from typing import Any

from sanket.schema import OCTANTS, Answer, EvaluationResult, Task


def score_single(task: Task, parsed_answer: Answer | None) -> bool:
    """Exact-match comparison between parsed option and gold answer.

    Args:
        task: Benchmark task instance.
        parsed_answer: Parsed model answer option (or None if unparseable).

    Returns:
        True if exact match, False otherwise.
    """
    if parsed_answer is None:
        return False
    return parsed_answer == task.gold


def wilson_score_interval(
    successes: int, total: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Calculate the Wilson score confidence interval for a binomial proportion.

    Args:
        successes: Number of successful trials.
        total: Total number of trials.
        confidence: Desired confidence level (default 0.95).

    Returns:
        Tuple of (lower_bound, upper_bound) in [0.0, 1.0].
    """
    if total <= 0:
        return (0.0, 0.0)

    # Standard z-score for 95% confidence interval
    z = 1.95996 if abs(confidence - 0.95) < 0.01 else 1.96

    p_hat = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = p_hat + z2 / (2.0 * total)
    radicand = (p_hat * (1.0 - p_hat) / total) + (z2 / (4.0 * total * total))
    margin = z * math.sqrt(max(0.0, radicand))

    lower = max(0.0, (center - margin) / denom)
    upper = min(1.0, (center + margin) / denom)
    return (round(lower, 4), round(upper, 4))


def compute_metrics(results: list[EvaluationResult]) -> dict[str, Any]:
    """Calculate aggregate benchmark metrics across a collection of evaluation results.

    Metrics computed:
    - Overall accuracy and 95% Wilson confidence interval
    - Accuracy broken down by question type (qtype)
    - Accuracy broken down by evaluation mode (image vs text)
    - Hallucination rate (directional choice when gold is NOT_INDICATED)
    - Counterfactual pair consistency (both pair members correct)
    - Perception gap (image mode accuracy minus text mode accuracy)

    Args:
        results: List of evaluated task results.

    Returns:
        Dictionary containing structured metrics.
    """
    if not results:
        return {
            "total": 0,
            "correct": 0,
            "accuracy": 0.0,
            "wilson_95": (0.0, 0.0),
            "unparseable": 0,
            "by_qtype": {},
            "by_mode": {},
            "hallucination_rate": None,
            "pair_consistency": None,
            "perception_gap": None,
        }

    total = len(results)
    correct = sum(1 for r in results if r.correct)
    unparseable = sum(1 for r in results if r.parsed_answer is None)
    acc = correct / total
    wilson_overall = wilson_score_interval(correct, total)

    # Breakdown by question type
    by_qtype_groups: dict[str, list[EvaluationResult]] = defaultdict(list)
    for r in results:
        by_qtype_groups[r.qtype].append(r)

    by_qtype: dict[str, dict[str, Any]] = {}
    for qtype, group in sorted(by_qtype_groups.items()):
        grp_tot = len(group)
        grp_cor = sum(1 for r in group if r.correct)
        by_qtype[qtype] = {
            "total": grp_tot,
            "correct": grp_cor,
            "accuracy": round(grp_cor / grp_tot, 4),
            "wilson_95": wilson_score_interval(grp_cor, grp_tot),
        }

    # Breakdown by mode
    by_mode_groups: dict[str, list[EvaluationResult]] = defaultdict(list)
    for r in results:
        by_mode_groups[r.mode].append(r)

    by_mode: dict[str, dict[str, Any]] = {}
    for mode, group in sorted(by_mode_groups.items()):
        grp_tot = len(group)
        grp_cor = sum(1 for r in group if r.correct)
        by_mode[mode] = {
            "total": grp_tot,
            "correct": grp_cor,
            "accuracy": round(grp_cor / grp_tot, 4),
            "wilson_95": wilson_score_interval(grp_cor, grp_tot),
        }

    # Hallucination rate: answered a direction when gold was NOT_INDICATED
    absent_results = [r for r in results if r.gold == "NOT_INDICATED"]
    if absent_results:
        hallucinated = sum(1 for r in absent_results if r.parsed_answer in OCTANTS)
        hallucination_rate = round(hallucinated / len(absent_results), 4)
    else:
        hallucination_rate = None

    # Pair consistency: both members (a and b) correct
    pairs_by_id: dict[str, list[EvaluationResult]] = defaultdict(list)
    for r in results:
        if r.pair_id:
            pairs_by_id[r.pair_id].append(r)

    complete_pairs = [pair for pair in pairs_by_id.values() if len(pair) == 2]
    if complete_pairs:
        consistent_pairs = sum(1 for pair in complete_pairs if pair[0].correct and pair[1].correct)
        pair_consistency = round(consistent_pairs / len(complete_pairs), 4)
    else:
        pair_consistency = None

    # Perception gap: image accuracy - text accuracy
    if "image" in by_mode and "text" in by_mode:
        perception_gap = round(by_mode["image"]["accuracy"] - by_mode["text"]["accuracy"], 4)
    else:
        perception_gap = None

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(acc, 4),
        "wilson_95": wilson_overall,
        "unparseable": unparseable,
        "by_qtype": by_qtype,
        "by_mode": by_mode,
        "hallucination_rate": hallucination_rate,
        "pair_consistency": pair_consistency,
        "perception_gap": perception_gap,
    }


__all__ = ["compute_metrics", "score_single", "wilson_score_interval"]
