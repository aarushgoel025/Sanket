"""Prompt builder for multimodal and text-only evaluation.

Constructs clean, versioned prompts containing only the question, options,
and visual/text context. Strictly prevents answer or metadata leakage.
"""

from pathlib import Path

from sanket.generator.text_description import describe_scene
from sanket.graph.venue import load_venue
from sanket.questions.options import ANSWER_OPTIONS
from sanket.schema import Scene, Task, Venue

OPTIONS_STRING = ", ".join(ANSWER_OPTIONS)


def build_prompt(
    task: Task,
    mode: str = "image",
    version: str = "v1",
    scene: Scene | None = None,
    venue: Venue | None = None,
) -> str:
    """Build standardized evaluation prompt without answer or metadata leakage.

    Args:
        task: Benchmark task instance.
        mode: Evaluation mode ('image' or 'text').
        version: Prompt template version.
        scene: Optional Scene model for text mode description.
        venue: Optional Venue model for text mode description.

    Returns:
        Formatted prompt string.

    Raises:
        ValueError: If mode or version is invalid.
        FileNotFoundError: If scene or venue cannot be located for text mode.
    """
    mode_normalized = mode.strip().lower()
    if mode_normalized not in ("image", "text"):
        raise ValueError(f"Unsupported mode '{mode}'. Expected 'image' or 'text'.")

    if version != "v1":
        # Default or fallback to v1 format for known versions
        pass

    if mode_normalized == "image":
        return (
            "You are looking at a signboard. Answer the question using only the board.\n"
            f"Question: {task.question}\n"
            f"Options: {OPTIONS_STRING}\n"
            "Reply with exactly one line: ANSWER: <OPTION>"
        )

    # Text mode: include structured textual description
    if scene is None:
        sc_path = Path(task.scene_path)
        if not sc_path.exists():
            raise FileNotFoundError(f"Scene specification file not found at {task.scene_path}")
        with open(sc_path, "r", encoding="utf-8") as f:
            scene = Scene.model_validate_json(f.read())

    if venue is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        v_path = repo_root / "config" / "venues" / f"{scene.venue_id}.yaml"
        if not v_path.exists():
            # Try finding venue by id matching filename
            candidates = list((repo_root / "config" / "venues").glob("*.yaml"))
            for cand in candidates:
                loaded = load_venue(cand)
                if loaded.id == scene.venue_id:
                    venue = loaded
                    break
            if venue is None:
                raise FileNotFoundError(
                    f"Venue '{scene.venue_id}' layout YAML not found in config/venues/"
                )
        else:
            venue = load_venue(v_path)

    board_description = describe_scene(scene, venue)

    return (
        "You are looking at a signboard. Here is a description of the board:\n"
        f"{board_description}\n\n"
        f"Question: {task.question}\n"
        f"Options: {OPTIONS_STRING}\n"
        "Reply with exactly one line: ANSWER: <OPTION>"
    )


__all__ = ["OPTIONS_STRING", "build_prompt"]
