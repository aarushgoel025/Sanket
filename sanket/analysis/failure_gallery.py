"""Failure gallery generator for model qualitative error analysis.

Extracts representative failure cases per model, formatted as clean Markdown
tables with relative image links, question text, gold targets, and model predictions.
"""

from pathlib import Path
from typing import Any

import pandas as pd


def select_model_failures(
    df: pd.DataFrame,
    model_id: str,
    max_cases: int = 5,
    mode: str = "image",
) -> list[dict[str, Any]]:
    """Select 3 to 5 representative failure cases for a model across distinct qtypes.

    Args:
        df: Consolidated evaluation results DataFrame.
        model_id: Model identifier to inspect.
        max_cases: Maximum number of failures to return (3 to 5).
        mode: Preferred evaluation mode ('image').

    Returns:
        List of failure record dictionaries.
    """
    if df.empty:
        return []

    # Filter to model failures in specified mode
    cond = (df["model_id"] == model_id) & (~df["correct"]) & (df["mode"] == mode)
    model_failures = df[cond].copy()

    if model_failures.empty:
        # Fallback to any mode if image mode has no failures
        model_failures = df[(df["model_id"] == model_id) & (~df["correct"])].copy()

    if model_failures.empty:
        return []

    # Prioritize selecting across diverse question types
    selected_records: list[dict[str, Any]] = []
    seen_qtypes: set[str] = set()

    # Pass 1: One failure per unique question type
    for _, row in model_failures.iterrows():
        qtype = str(row.get("qtype", "UNKNOWN"))
        if qtype not in seen_qtypes:
            seen_qtypes.add(qtype)
            selected_records.append(row.to_dict())
            if len(selected_records) >= max_cases:
                break

    # Pass 2: Fill remaining up to max_cases if needed
    if len(selected_records) < max_cases:
        chosen_ids = {r["task_id"] for r in selected_records}
        for _, row in model_failures.iterrows():
            if row["task_id"] not in chosen_ids:
                selected_records.append(row.to_dict())
                if len(selected_records) >= max_cases:
                    break

    return selected_records


def generate_failure_gallery_markdown(
    df: pd.DataFrame,
    tasks_map: dict[str, dict[str, Any]] | None = None,
    reports_dir: Path | str = "reports",
    max_per_model: int = 4,
) -> str:
    """Generate Markdown gallery table displaying failure cases per model.

    Args:
        df: Consolidated evaluation results DataFrame.
        tasks_map: Optional dictionary mapping task_id to Task metadata/paths.
        reports_dir: Base directory for resolving relative image links.
        max_per_model: Number of failure examples per model (default 4).

    Returns:
        Markdown formatted string.
    """
    if df.empty:
        return "*No evaluation results available for failure gallery.*\n"

    base_dir = Path(reports_dir)
    models = sorted(df["model_id"].unique())
    lines: list[str] = [
        "## Qualitative Failure Gallery\n",
        (
            "Representative error cases where models produced incorrect orientations, "
            "misbound symbols, or hallucinated nonexistent destinations.\n"
        ),
    ]

    for model_id in models:
        failures = select_model_failures(df, model_id=model_id, max_cases=max_per_model)
        lines.append(f"### Model: `{model_id}`\n")

        if not failures:
            lines.append("*No failure cases recorded for this model.*\n")
            continue

        lines.append(
            "| Task ID | Type | Signboard Image | Question | Gold Reference | Model Answer |"
        )
        lines.append("|---|---|:---:|---|:---:|:---:|")

        for case in failures:
            tid = case.get("task_id", "")
            qtype = case.get("qtype", "DIRECT")
            gold = case.get("gold", "UNKNOWN")
            pred = case.get("parsed_answer", "None") or "Unparseable"

            # Retrieve image and question from tasks_map or case
            task_info = tasks_map.get(tid, {}) if tasks_map else {}
            question = (
                task_info.get("question")
                or case.get("question")
                or f"Wayfinding to destination for {tid}"
            )
            raw_img_path = (
                task_info.get("image_path")
                or case.get("image_path")
                or f"data/full_dataset/images/{tid}.png"
            )

            # Format relative image path for Markdown rendering
            try:
                rel_img_path = Path(raw_img_path).relative_to(base_dir).as_posix()
            except ValueError:
                # Fallback to standard project-relative path
                rel_img_path = (Path("..") / raw_img_path).as_posix()

            img_cell = f"![{tid}]({rel_img_path})"

            lines.append(
                f"| `{tid}` | **{qtype}** | {img_cell} | {question} | `{gold}` | **`{pred}`** |"
            )

        lines.append("")

    return "\n".join(lines)


__all__ = [
    "generate_failure_gallery_markdown",
    "select_model_failures",
]
