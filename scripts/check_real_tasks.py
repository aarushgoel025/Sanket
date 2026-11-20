"""Integrity verification script for hand-labelled real signboard tasks.

Enforces:
1. Every task references an existing image file on disk.
2. The image contains NO EXIF metadata (privacy/ethics rule).
3. The gold answer is a valid option from the fixed canonical ANSWER_OPTIONS set.
4. The options list matches ANSWER_OPTIONS in exact contract order.
5. Question and hand-labelling notes are non-empty.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sanket.schema import ANSWER_OPTIONS, Task
from scripts.strip_exif import has_exif


def resolve_image_path(image_path_str: str, base_dir: Path) -> Path:
    """Resolve an image path string against current directory and base directory."""
    raw_path = Path(image_path_str)
    if raw_path.exists():
        return raw_path

    # Try relative to base_dir (e.g. data/real_photos)
    candidate_1 = base_dir / raw_path
    if candidate_1.exists():
        return candidate_1

    # Try relative to base_dir / "images"
    candidate_2 = base_dir / "images" / raw_path.name
    if candidate_2.exists():
        return candidate_2

    return candidate_1


def check_real_task_entry(
    entry: dict[str, Any],
    line_no: int,
    base_dir: Path,
) -> Task:
    """Validate a single real task dictionary against all acceptance rules.

    Args:
        entry: Parsed dictionary from a line of real_tasks.jsonl.
        line_no: Line number in the file (for diagnostic reporting).
        base_dir: Directory containing real_tasks.jsonl.

    Returns:
        Validated Task pydantic instance.

    Raises:
        ValueError: If any validation rule fails.
    """
    task_id = str(entry.get("task_id", "")).strip()
    if not task_id:
        raise ValueError(f"Line {line_no}: Missing or empty 'task_id'.")

    # 1. Question check
    question = str(entry.get("question", "")).strip()
    if not question:
        raise ValueError(f"Task '{task_id}' (line {line_no}): Missing or empty 'question'.")

    # 2. Options check
    options = entry.get("options")
    if not isinstance(options, list):
        raise TypeError(f"Task '{task_id}' (line {line_no}): 'options' must be a list.")
    if options != ANSWER_OPTIONS:
        raise ValueError(
            f"Task '{task_id}' (line {line_no}): 'options' must match fixed ANSWER_OPTIONS exactly: "
            f"expected {ANSWER_OPTIONS}, got {options}"
        )

    # 3. Gold answer check
    gold = entry.get("gold")
    if gold not in ANSWER_OPTIONS:
        raise ValueError(
            f"Task '{task_id}' (line {line_no}): Gold answer '{gold}' is not a valid option. "
            f"Must be one of: {ANSWER_OPTIONS}"
        )

    # 4. Notes check
    notes = str(entry.get("notes", "")).strip()
    if not notes:
        raise ValueError(
            f"Task '{task_id}' (line {line_no}): Missing 'notes' field (must specify 'hand-labelled by <initials>')."
        )

    # 5. Image path check
    raw_img_path = str(entry.get("image_path", "")).strip()
    if not raw_img_path:
        raise ValueError(f"Task '{task_id}' (line {line_no}): Missing or empty 'image_path'.")

    resolved_img = resolve_image_path(raw_img_path, base_dir)
    if not resolved_img.exists():
        raise FileNotFoundError(
            f"Task '{task_id}' (line {line_no}): Image file not found at '{resolved_img}' (raw: '{raw_img_path}')."
        )

    # 6. EXIF check
    if has_exif(resolved_img):
        raise ValueError(
            f"Task '{task_id}' (line {line_no}): Image '{resolved_img}' contains EXIF metadata! "
            f"Run 'python scripts/strip_exif.py' before committing."
        )

    # Construct Task instance
    task = Task(
        task_id=task_id,
        qtype="REAL",
        question=question,
        options=options,
        gold=gold,
        image_path=str(resolved_img),
        notes=notes,
        task_set="real",
    )
    return task


def check_real_tasks_file(
    tasks_file: Path | str = "data/real_photos/real_tasks.jsonl",
) -> list[Task]:
    """Verify all real tasks in a JSONL file.

    Args:
        tasks_file: Path to real_tasks.jsonl.

    Returns:
        List of validated Task instances.

    Raises:
        FileNotFoundError: If tasks file does not exist.
        ValueError: If file is empty or any task fails validation.
    """
    t_path = Path(tasks_file)
    if not t_path.exists():
        raise FileNotFoundError(f"Real tasks file not found: {t_path}")

    base_dir = t_path.parent
    validated_tasks: list[Task] = []
    seen_ids: set[str] = set()

    with open(t_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {idx} in {t_path} is invalid JSON: {exc}") from exc

            task = check_real_task_entry(entry, line_no=idx, base_dir=base_dir)
            if task.task_id in seen_ids:
                raise ValueError(f"Duplicate task_id '{task.task_id}' found at line {idx}.")
            seen_ids.add(task.task_id)
            validated_tasks.append(task)

    if not validated_tasks:
        raise ValueError(f"Real tasks file '{t_path}' contains no tasks.")

    return validated_tasks


def main() -> int:
    """CLI entrypoint for check_real_tasks."""
    parser = argparse.ArgumentParser(
        description="Verify integrity of hand-labelled real signboard tasks."
    )
    parser.add_argument(
        "--tasks-file",
        "-t",
        type=Path,
        default=Path("data/real_photos/real_tasks.jsonl"),
        help="Path to real_tasks.jsonl (default: data/real_photos/real_tasks.jsonl)",
    )
    args = parser.parse_args()

    print(f"Checking real tasks file: {args.tasks_file}")
    try:
        tasks = check_real_tasks_file(args.tasks_file)
    except (ValueError, TypeError, FileNotFoundError, OSError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"SUCCESS: {len(tasks)} real tasks verified cleanly:")
    for t in tasks:
        print(f"  - [{t.task_id}] gold={t.gold:12s} | image={t.image_path} | notes={t.notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
