"""Unit tests for evaluation metrics, Wilson intervals, figures, and reporting.

Verifies:
- Wilson score interval on known mathematical values (e.g. 8/10 at 95%).
- Correct computation of overall, qtype, and knob-binned accuracy.
- Minimal-pair consistency rate calculation.
- Hallucination rate on unlisted (ABSENT) destinations.
- Perception gap calculation (text mode minus image mode).
- Generation of validation_report.md, findings_report.md, and figures F1-F6.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from sanket.analysis.metrics import (
    compute_accuracy_by_knob,
    compute_accuracy_by_qtype,
    compute_hallucination_rate,
    compute_overall_metrics,
    compute_pair_consistency,
    compute_perception_gap,
    wilson_interval,
)
from sanket.analysis.report import run_reporting


def test_wilson_interval_known_values() -> None:
    """Verify Wilson score confidence interval matches exact mathematical standards.

    Acceptance criterion: Wilson interval tested on known values (e.g. 8/10 at 95%).
    For k=8, n=10, z=1.95996:
      center = (0.8 + 1.95996^2 / 20) / (1 + 1.95996^2 / 10) = 0.71674
      margin = 1.95996 * sqrt(0.8*0.2/10 + 1.95996^2 / 400) / (1 + 1.95996^2 / 10) = 0.22658
      lower = 0.4902, upper = 0.9433
    """
    # 8/10 at 95%
    low, high = wilson_interval(8, 10, confidence=0.95)
    assert low == 0.4902
    assert high == 0.9433

    # Boundary conditions
    assert wilson_interval(0, 0) == (0.0, 0.0)

    # 0/10 successes
    low_0, high_0 = wilson_interval(0, 10)
    assert low_0 == 0.0
    assert 0.25 <= high_0 <= 0.32

    # 10/10 successes
    low_10, high_10 = wilson_interval(10, 10)
    assert 0.68 <= low_10 <= 0.75
    assert high_10 == 1.0

    # 50/100 (symmetric around 0.5)
    low_50, high_50 = wilson_interval(50, 100)
    assert low_50 < 0.50 < high_50
    assert round(low_50 + high_50, 2) == 1.0


@pytest.fixture
def mock_results_df() -> pd.DataFrame:
    """Construct a controlled DataFrame of evaluation results for testing."""
    records = [
        # Model A: image mode
        {
            "task_id": "t1",
            "model_id": "model_a",
            "mode": "image",
            "qtype": "DIRECT",
            "gold": "RIGHT",
            "parsed_answer": "RIGHT",
            "correct": True,
            "pair_id": "p1",
            "n_entries": 3,
            "perspective_deg": 5.0,
            "clutter": 0,
            "scripts": "en",
        },
        {
            "task_id": "t2",
            "model_id": "model_a",
            "mode": "image",
            "qtype": "DIRECT",
            "gold": "LEFT",
            "parsed_answer": "LEFT",
            "correct": True,
            "pair_id": "p1",
            "n_entries": 3,
            "perspective_deg": 5.0,
            "clutter": 0,
            "scripts": "en",
        },
        {
            "task_id": "t3",
            "model_id": "model_a",
            "mode": "image",
            "qtype": "BINDING",
            "gold": "AHEAD",
            "parsed_answer": "RIGHT",
            "correct": False,
            "pair_id": "p2",
            "n_entries": 6,
            "perspective_deg": 20.0,
            "clutter": 3,
            "scripts": "en+hi",
        },
        {
            "task_id": "t4",
            "model_id": "model_a",
            "mode": "image",
            "qtype": "ABSENT",
            "gold": "NOT_INDICATED",
            "parsed_answer": "AHEAD",
            "correct": False,
            "pair_id": None,
            "n_entries": 4,
            "perspective_deg": 10.0,
            "clutter": 1,
            "scripts": "en",
        },
        {
            "task_id": "t5",
            "model_id": "model_a",
            "mode": "image",
            "qtype": "ABSENT",
            "gold": "NOT_INDICATED",
            "parsed_answer": "NOT_INDICATED",
            "correct": True,
            "pair_id": None,
            "n_entries": 4,
            "perspective_deg": 10.0,
            "clutter": 1,
            "scripts": "en",
        },
        # Model A: text mode
        {
            "task_id": "t1",
            "model_id": "model_a",
            "mode": "text",
            "qtype": "DIRECT",
            "gold": "RIGHT",
            "parsed_answer": "RIGHT",
            "correct": True,
            "pair_id": "p1",
            "n_entries": 3,
            "perspective_deg": 5.0,
            "clutter": 0,
            "scripts": "en",
        },
        {
            "task_id": "t2",
            "model_id": "model_a",
            "mode": "text",
            "qtype": "DIRECT",
            "gold": "LEFT",
            "parsed_answer": "LEFT",
            "correct": True,
            "pair_id": "p1",
            "n_entries": 3,
            "perspective_deg": 5.0,
            "clutter": 0,
            "scripts": "en",
        },
        {
            "task_id": "t3",
            "model_id": "model_a",
            "mode": "text",
            "qtype": "BINDING",
            "gold": "AHEAD",
            "parsed_answer": "AHEAD",
            "correct": True,
            "pair_id": "p2",
            "n_entries": 6,
            "perspective_deg": 20.0,
            "clutter": 3,
            "scripts": "en+hi",
        },
        {
            "task_id": "t4",
            "model_id": "model_a",
            "mode": "text",
            "qtype": "ABSENT",
            "gold": "NOT_INDICATED",
            "parsed_answer": "NOT_INDICATED",
            "correct": True,
            "pair_id": None,
            "n_entries": 4,
            "perspective_deg": 10.0,
            "clutter": 1,
            "scripts": "en",
        },
        {
            "task_id": "t5",
            "model_id": "model_a",
            "mode": "text",
            "qtype": "ABSENT",
            "gold": "NOT_INDICATED",
            "parsed_answer": "NOT_INDICATED",
            "correct": True,
            "pair_id": None,
            "n_entries": 4,
            "perspective_deg": 10.0,
            "clutter": 1,
            "scripts": "en",
        },
    ]
    df = pd.DataFrame(records)
    df["n_entries_bin"] = pd.cut(df["n_entries"], bins=[0, 3, 5, 10], labels=["2-3", "4-5", "6-8"])
    df["perspective_bin"] = pd.cut(
        df["perspective_deg"],
        bins=[-0.1, 8.0, 18.0, 30.0],
        labels=["0-8°", "9-17°", "18-25°"],
    )
    df["clutter_bin"] = pd.cut(df["clutter"], bins=[-1, 0, 2, 10], labels=["0", "1-2", "3-6"])
    return df


def test_overall_metrics_calculation(mock_results_df: pd.DataFrame) -> None:
    """Verify compute_overall_metrics groups by model and mode accurately."""
    overall = compute_overall_metrics(mock_results_df)

    img_row = overall[(overall["model_id"] == "model_a") & (overall["mode"] == "image")].iloc[0]
    txt_row = overall[(overall["model_id"] == "model_a") & (overall["mode"] == "text")].iloc[0]

    # Image: 3 correct out of 5 = 60%
    assert img_row["total"] == 5
    assert img_row["correct"] == 3
    assert img_row["accuracy"] == 0.60
    assert img_row["wilson_low"] < 0.60 < img_row["wilson_high"]

    # Text: 5 correct out of 5 = 100%
    assert txt_row["total"] == 5
    assert txt_row["correct"] == 5
    assert txt_row["accuracy"] == 1.0


def test_accuracy_by_qtype_and_knob(mock_results_df: pd.DataFrame) -> None:
    """Verify segmented accuracy calculations by question type and knob bins."""
    by_qtype = compute_accuracy_by_qtype(mock_results_df)
    direct_img = by_qtype[(by_qtype["qtype"] == "DIRECT") & (by_qtype["mode"] == "image")].iloc[0]
    assert direct_img["total"] == 2
    assert direct_img["correct"] == 2
    assert direct_img["accuracy"] == 1.0

    by_knob = compute_accuracy_by_knob(mock_results_df, "n_entries_bin")
    entries_2_3 = by_knob[(by_knob["n_entries_bin"] == "2-3") & (by_knob["mode"] == "image")].iloc[
        0
    ]
    assert entries_2_3["accuracy"] == 1.0


def test_pair_consistency_calculation(mock_results_df: pd.DataFrame) -> None:
    """Verify minimal-pair consistency identifies pairs where both members succeeded."""
    pair_metrics = compute_pair_consistency(mock_results_df)

    # In mock data, only p1 is a complete pair (t1 and t2 both in p1).
    # For model_a in image mode: both t1 and t2 are correct -> 1 consistent pair out of 1.
    img_pair = pair_metrics[pair_metrics["mode"] == "image"].iloc[0]
    assert img_pair["total_pairs"] == 1
    assert img_pair["consistent_pairs"] == 1
    assert img_pair["pair_consistency"] == 1.0


def test_hallucination_rate_on_absent(mock_results_df: pd.DataFrame) -> None:
    """Verify hallucination rate detects directional responses when gold is NOT_INDICATED."""
    halluc = compute_hallucination_rate(mock_results_df)
    img_halluc = halluc[halluc["mode"] == "image"].iloc[0]

    # Two absent tasks (t4 and t5). t4 parsed as 'AHEAD' (hallucinated), t5 parsed as 'NOT_INDICATED'.
    assert img_halluc["absent_count"] == 2
    assert img_halluc["hallucinated_count"] == 1
    assert img_halluc["hallucination_rate"] == 0.50


def test_perception_gap_calculation(mock_results_df: pd.DataFrame) -> None:
    """Verify perception gap computes text accuracy minus image accuracy."""
    gap_df = compute_perception_gap(mock_results_df)
    row = gap_df[gap_df["model_id"] == "model_a"].iloc[0]

    # Text accuracy = 1.0 (100%), Image accuracy = 0.6 (60%) -> Gap = +0.40
    assert row["image_acc"] == 0.60
    assert row["text_acc"] == 1.0
    assert row["perception_gap"] == 0.40


def test_generate_figures_and_reports(tmp_path: Path) -> None:
    """Verify that report and figure generation produces valid files on disk."""
    # 1. Setup mock tasks.jsonl
    tasks_file = tmp_path / "tasks.jsonl"
    results_file = tmp_path / "results.jsonl"
    consequences_file = tmp_path / "consequences.yaml"
    reports_dir = tmp_path / "reports"

    consequences_file.write_text(
        "consequences:\n"
        "  DIRECT:\n    summary: Wrong turn\n    impact: Delayed transit\n"
        "  BINDING:\n    summary: Wrong platform\n    impact: Missed service\n"
        "  CLOSURE:\n    summary: Blocked gate\n    impact: Barricade delay\n"
        "  OVERRIDE:\n    summary: Detour ignored\n    impact: Hazard zone\n"
        "  EGOCENTRIC:\n    summary: Disorientation\n    impact: Opposite way\n"
        "  ABSENT:\n    summary: Hallucination\n    impact: Wandering\n",
        encoding="utf-8",
    )

    tasks_records = [
        {
            "task_id": f"task_{i}",
            "schema_version": "1.0.0",
            "generator_version": "1.0.0",
            "seed": 100 + i,
            "qtype": "DIRECT",
            "question": f"Where is Platform {i}?",
            "options": ["AHEAD", "RIGHT", "LEFT", "CLOSED", "NOT_INDICATED"],
            "gold": "RIGHT",
            "image_path": f"/fake/images/task_{i}.png",
            "scene_path": f"/fake/scenes/task_{i}.json",
            "target_dest_id": "p1",
            "receipt": {
                "solver_answer": "RIGHT",
                "independent_answer": "RIGHT",
                "agree": True,
                "fidelity_ok": True,
                "visibility_ok": True,
                "evidence_visible_ratio": 1.0,
            },
        }
        for i in range(10)
    ]
    with open(tasks_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in tasks_records)

    results_records = [
        {
            "task_id": f"task_{i}",
            "model_id": "oracle_test",
            "mode": "image",
            "prompt_version": "v1",
            "gold": "RIGHT",
            "parsed_answer": "RIGHT",
            "correct": True,
            "raw_text": "ANSWER: RIGHT",
            "latency_s": 0.01,
            "timestamp": 12345.0,
            "qtype": "DIRECT",
        }
        for i in range(10)
    ]
    with open(results_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in results_records)

    # 2. Run reporting pipeline
    val_file, find_file = run_reporting(
        tasks_path=tasks_file,
        results_path=results_file,
        reports_dir=reports_dir,
    )

    # 3. Assertions on generated reports
    assert val_file.exists()
    assert find_file.exists()

    val_content = val_file.read_text(encoding="utf-8")
    assert "# Dataset Validation Report" in val_content
    assert "Verification Receipts" in val_content
    assert "Human Audit" in val_content

    find_content = find_file.read_text(encoding="utf-8")
    assert "# Model Findings and Evaluation Report" in find_content
    assert "Multimodal Perception Gap" in find_content
    assert "oracle_test" in find_content

    # 4. Assertions on figures F1 to F6
    figures_dir = reports_dir / "figures"
    expected_figures = [
        "F1_model_skill_heatmap.png",
        "F2_difficulty_curves.png",
        "F3_perception_gap.png",
        "F4_hallucination_absent.png",
        "F5_synthetic_vs_real.png",
        "F6_pair_consistency.png",
    ]
    for fig_name in expected_figures:
        fig_path = figures_dir / fig_name
        assert fig_path.exists(), f"Expected figure {fig_name} was not created"
        assert fig_path.stat().st_size > 1000
