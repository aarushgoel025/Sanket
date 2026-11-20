"""Benchmark evaluation metrics and slicing using pandas.

Provides:
- Wilson score 95% confidence intervals
- Overall and segmented accuracy (by qtype, knob bins, model, mode)
- Minimal-pair consistency rates
- Hallucination rate on absent destinations
- Perception gap (text mode accuracy minus image mode accuracy)
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sanket.schema import ANSWER_OPTIONS, OCTANTS

# Z-score for standard 95% confidence interval
Z_95 = 1.959963984540054


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Compute standard two-sided Wilson score confidence interval.

    Args:
        successes: Number of successful outcomes (k >= 0).
        total: Number of total trials (n >= 0).
        confidence: Desired confidence level (default 0.95).

    Returns:
        Tuple of (lower_bound, upper_bound) rounded to 4 decimal places.
    """
    if total <= 0:
        return 0.0, 0.0

    k = float(successes)
    n = float(total)
    p_hat = k / n

    # Map standard confidence levels or use exact z for 0.95
    if abs(confidence - 0.95) < 1e-4:
        z = Z_95
    else:
        # Simple approximation for other levels if needed
        z = 1.95996

    z2 = z * z
    denom = 1.0 + (z2 / n)
    center = (p_hat + (z2 / (2.0 * n))) / denom
    spread = (z * np.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n)))) / denom

    low = max(0.0, center - spread)
    high = min(1.0, center + spread)

    return round(float(low), 4), round(float(high), 4)


def load_dataset_and_results(
    results_path: Path | str,
    tasks_path: Path | str | None = None,
) -> pd.DataFrame:
    """Load evaluation results JSONL and optionally join with task specifications.

    Args:
        results_path: Path to reports/results.jsonl.
        tasks_path: Optional path to data/full_dataset/tasks.jsonl.

    Returns:
        Consolidated pandas DataFrame.
    """
    results_file = Path(results_path)
    if not results_file.exists():
        return pd.DataFrame()

    results_data: list[dict[str, Any]] = []
    with open(results_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    results_data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not results_data:
        return pd.DataFrame()

    df_results = pd.DataFrame(results_data)

    # Attach task metadata if available
    tasks_map: dict[str, dict[str, Any]] = {}
    if tasks_path:
        t_file = Path(tasks_path)
        if t_file.exists():
            with open(t_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            td = json.loads(line)
                            tasks_map[td["task_id"]] = td
                        except json.JSONDecodeError:
                            continue

    if tasks_map:
        # Extract knobs from task metadata or scene
        knob_records: list[dict[str, Any]] = []
        for tid in df_results["task_id"]:
            t_obj = tasks_map.get(tid, {})
            # Look inside receipt or custom fields
            knobs = t_obj.get("knobs", {})
            knob_records.append(
                {
                    "task_id": tid,
                    "n_entries": knobs.get("n_entries", 4),
                    "perspective_deg": knobs.get("perspective_deg", 0.0),
                    "blur": knobs.get("blur", 0.0),
                    "noise": knobs.get("noise", 0.0),
                    "lighting": knobs.get("lighting", 0.0),
                    "clutter": knobs.get("clutter", 0),
                    "occlusion": knobs.get("occlusion", 0.0),
                    "jpeg_quality": knobs.get("jpeg_quality", 95),
                    "template": knobs.get("template", "board_list"),
                    "scripts": "+".join(knobs.get("scripts", ["en"])),
                }
            )
        df_knobs = pd.DataFrame(knob_records).drop_duplicates(subset=["task_id"])
        df = df_results.merge(df_knobs, on="task_id", how="left")
    else:
        df = df_results.copy()
        # Ensure default knob columns exist if missing
        for col in ["n_entries", "perspective_deg", "clutter"]:
            if col not in df.columns:
                df[col] = 0
        if "scripts" not in df.columns:
            df["scripts"] = "en"

    # Add binning columns for knobs
    df["n_entries_bin"] = pd.cut(
        df["n_entries"].fillna(4),
        bins=[0, 3, 5, 10],
        labels=["2-3", "4-5", "6-8"],
    )
    df["perspective_bin"] = pd.cut(
        df["perspective_deg"].fillna(0.0),
        bins=[-0.1, 8.0, 18.0, 30.0],
        labels=["0-8°", "9-17°", "18-25°"],
    )
    df["clutter_bin"] = pd.cut(
        df["clutter"].fillna(0),
        bins=[-1, 0, 2, 10],
        labels=["0", "1-2", "3-6"],
    )

    if "task_set" not in df.columns:
        df["task_set"] = "synthetic"
    is_real = df["task_id"].astype(str).str.startswith("R") | (
        df.get("qtype", pd.Series(dtype=str)) == "REAL"
    )
    df.loc[is_real, "task_set"] = "real"

    return df


def compute_overall_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute overall accuracy and 95% Wilson intervals grouped by model and mode."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "total",
                "correct",
                "accuracy",
                "wilson_low",
                "wilson_high",
            ]
        )

    grouped = (
        df.groupby(["model_id", "mode"])
        .agg(
            total=("correct", "count"),
            correct=("correct", "sum"),
        )
        .reset_index()
    )

    grouped["accuracy"] = (grouped["correct"] / grouped["total"]).round(4)

    intervals = [
        wilson_interval(int(row["correct"]), int(row["total"])) for _, row in grouped.iterrows()
    ]
    grouped["wilson_low"] = [iv[0] for iv in intervals]
    grouped["wilson_high"] = [iv[1] for iv in intervals]

    return grouped


def compute_accuracy_by_qtype(df: pd.DataFrame) -> pd.DataFrame:
    """Compute accuracy and Wilson intervals grouped by model, mode, and question type."""
    if df.empty or "qtype" not in df.columns:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "qtype",
                "total",
                "correct",
                "accuracy",
                "wilson_low",
                "wilson_high",
            ]
        )

    grouped = (
        df.groupby(["model_id", "mode", "qtype"])
        .agg(
            total=("correct", "count"),
            correct=("correct", "sum"),
        )
        .reset_index()
    )

    grouped["accuracy"] = (grouped["correct"] / grouped["total"]).round(4)
    intervals = [
        wilson_interval(int(row["correct"]), int(row["total"])) for _, row in grouped.iterrows()
    ]
    grouped["wilson_low"] = [iv[0] for iv in intervals]
    grouped["wilson_high"] = [iv[1] for iv in intervals]

    return grouped


def compute_accuracy_by_knob(df: pd.DataFrame, knob_bin_col: str) -> pd.DataFrame:
    """Compute accuracy and Wilson intervals across bins of a difficulty knob."""
    if df.empty or knob_bin_col not in df.columns:
        return pd.DataFrame()

    grouped = (
        df.groupby(["model_id", "mode", knob_bin_col], observed=False)
        .agg(
            total=("correct", "count"),
            correct=("correct", "sum"),
        )
        .reset_index()
    )

    grouped["accuracy"] = (grouped["correct"] / grouped["total"]).round(4)
    intervals = [
        wilson_interval(int(row["correct"]), int(row["total"])) for _, row in grouped.iterrows()
    ]
    grouped["wilson_low"] = [iv[0] for iv in intervals]
    grouped["wilson_high"] = [iv[1] for iv in intervals]

    return grouped


def compute_pair_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Compute minimal-pair consistency rate (both pair members correct).

    Returns DataFrame grouped by model_id and mode.
    """
    if df.empty or "pair_id" not in df.columns:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "total_pairs",
                "consistent_pairs",
                "pair_consistency",
            ]
        )

    # Filter to items that belong to a pair
    paired = df[df["pair_id"].notna() & (df["pair_id"] != "")].copy()
    if paired.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "total_pairs",
                "consistent_pairs",
                "pair_consistency",
            ]
        )

    # Group by model, mode, and pair_id
    pair_status = (
        paired.groupby(["model_id", "mode", "pair_id"])
        .agg(
            pair_count=("correct", "count"),
            both_correct=("correct", "all"),
        )
        .reset_index()
    )

    # Only count complete pairs (size 2)
    complete_pairs = pair_status[pair_status["pair_count"] == 2]
    if complete_pairs.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "total_pairs",
                "consistent_pairs",
                "pair_consistency",
            ]
        )

    summary = (
        complete_pairs.groupby(["model_id", "mode"])
        .agg(
            total_pairs=("both_correct", "count"),
            consistent_pairs=("both_correct", "sum"),
        )
        .reset_index()
    )

    summary["pair_consistency"] = (summary["consistent_pairs"] / summary["total_pairs"]).round(4)
    return summary


def compute_hallucination_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Compute hallucination rate on ABSENT tasks (model asserts direction when gold is NOT_INDICATED)."""
    if df.empty or "gold" not in df.columns:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "absent_count",
                "hallucinated_count",
                "hallucination_rate",
            ]
        )

    absent_df = df[
        (df["gold"] == "NOT_INDICATED") | (df.get("qtype", pd.Series(dtype="str")) == "ABSENT")
    ].copy()

    if absent_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "mode",
                "absent_count",
                "hallucinated_count",
                "hallucination_rate",
            ]
        )

    # Hallucination = model selected one of the 8 physical directions (OCTANTS)
    absent_df["hallucinated"] = absent_df["parsed_answer"].isin(OCTANTS)

    summary = (
        absent_df.groupby(["model_id", "mode"])
        .agg(
            absent_count=("hallucinated", "count"),
            hallucinated_count=("hallucinated", "sum"),
        )
        .reset_index()
    )

    summary["hallucination_rate"] = (summary["hallucinated_count"] / summary["absent_count"]).round(
        4
    )
    return summary


def compute_perception_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Compute perception gap = accuracy(text) - accuracy(image) for each model."""
    if df.empty or "mode" not in df.columns:
        return pd.DataFrame(
            columns=[
                "model_id",
                "image_acc",
                "text_acc",
                "perception_gap",
            ]
        )

    overall = compute_overall_metrics(df)
    if overall.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "image_acc",
                "text_acc",
                "perception_gap",
            ]
        )

    pivoted = overall.pivot(index="model_id", columns="mode", values="accuracy").reset_index()

    if "image" not in pivoted.columns:
        pivoted["image"] = np.nan
    if "text" not in pivoted.columns:
        pivoted["text"] = np.nan

    pivoted = pivoted.rename(columns={"image": "image_acc", "text": "text_acc"})
    pivoted["perception_gap"] = (pivoted["text_acc"] - pivoted["image_acc"]).round(4)

    return pivoted[["model_id", "image_acc", "text_acc", "perception_gap"]].copy()


def compute_synthetic_vs_real_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-model accuracy and 95% Wilson confidence intervals on synthetic vs real tasks.

    Filters to image mode (since real signboard photographs are evaluated in image mode only).

    Returns:
        DataFrame with columns:
        - model_id: str
        - synth_total: int
        - synth_correct: int
        - synth_accuracy: float
        - synth_wilson_low: float
        - synth_wilson_high: float
        - real_total: int
        - real_correct: int
        - real_accuracy: float
        - real_wilson_low: float
        - real_wilson_high: float
        - accuracy_gap: float (real_accuracy - synth_accuracy)
    """
    cols = [
        "model_id",
        "synth_total",
        "synth_correct",
        "synth_accuracy",
        "synth_wilson_low",
        "synth_wilson_high",
        "real_total",
        "real_correct",
        "real_accuracy",
        "real_wilson_low",
        "real_wilson_high",
        "accuracy_gap",
    ]
    if df.empty or "model_id" not in df.columns:
        return pd.DataFrame(columns=cols)

    df_copy = df.copy()
    if "task_set" not in df_copy.columns:
        df_copy["task_set"] = "synthetic"
    is_real = df_copy["task_id"].astype(str).str.startswith("R") | (
        df_copy.get("qtype", pd.Series(dtype=str)) == "REAL"
    )
    df_copy.loc[is_real, "task_set"] = "real"

    # Restrict to image mode
    img_df = df_copy[df_copy["mode"] == "image"] if "mode" in df_copy.columns else df_copy

    models = sorted(img_df["model_id"].unique())
    if not models:
        return pd.DataFrame(columns=cols)

    rows: list[dict[str, Any]] = []
    for model_id in models:
        m_df = img_df[img_df["model_id"] == model_id]

        # Synthetic subset
        synth_sub = m_df[m_df["task_set"] != "real"]
        s_total = len(synth_sub)
        s_correct = int(synth_sub["correct"].sum()) if s_total > 0 else 0
        s_acc = round(float(s_correct / s_total), 4) if s_total > 0 else np.nan
        s_low, s_high = wilson_interval(s_correct, s_total) if s_total > 0 else (np.nan, np.nan)

        # Real subset
        real_sub = m_df[m_df["task_set"] == "real"]
        r_total = len(real_sub)
        r_correct = int(real_sub["correct"].sum()) if r_total > 0 else 0
        r_acc = round(float(r_correct / r_total), 4) if r_total > 0 else np.nan
        r_low, r_high = wilson_interval(r_correct, r_total) if r_total > 0 else (np.nan, np.nan)

        gap = round(float(r_acc - s_acc), 4) if not (np.isnan(r_acc) or np.isnan(s_acc)) else np.nan

        rows.append(
            {
                "model_id": model_id,
                "synth_total": s_total,
                "synth_correct": s_correct,
                "synth_accuracy": s_acc,
                "synth_wilson_low": s_low,
                "synth_wilson_high": s_high,
                "real_total": r_total,
                "real_correct": r_correct,
                "real_accuracy": r_acc,
                "real_wilson_low": r_low,
                "real_wilson_high": r_high,
                "accuracy_gap": gap,
            }
        )

    return pd.DataFrame(rows)


__all__ = [
    "ANSWER_OPTIONS",
    "OCTANTS",
    "compute_accuracy_by_knob",
    "compute_accuracy_by_qtype",
    "compute_hallucination_rate",
    "compute_overall_metrics",
    "compute_pair_consistency",
    "compute_perception_gap",
    "compute_synthetic_vs_real_metrics",
    "load_dataset_and_results",
    "wilson_interval",
]
