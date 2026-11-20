"""Question phrasing templates and task construction for wayfinding benchmarks.

Builds standardized question texts, derives reference gold answers exclusively from
the venue graph solver, and constructs auditable Task specifications.
"""

from typing import Literal

import numpy as np

from sanket.generator.scene_builder import SceneBuild
from sanket.graph.solver import gold_answer
from sanket.questions.options import ANSWER_OPTIONS, options_for_task
from sanket.schema import (
    Answer,
    Receipt,
    Task,
    Venue,
)

QuestionType = Literal["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]

BASE_SKILL_TAGS: dict[str, list[str]] = {
    "DIRECT": ["arrow_reading"],
    "BINDING": ["arrow_reading", "text_arrow_binding"],
    "CLOSURE": ["arrow_reading", "negation_closure"],
    "OVERRIDE": ["arrow_reading", "override_reasoning"],
    "EGOCENTRIC": ["arrow_reading", "egocentric_rotation"],
    "ABSENT": ["absence_detection"],
}

EGOCENTRIC_TURNS: list[tuple[int, str]] = [
    (180, "turn around (180 degrees)"),
    (90, "turn 90 degrees to your right"),
    (270, "turn 90 degrees to your left"),
]


def _infer_qtype(sb: SceneBuild) -> QuestionType:
    """Infer benchmark question type from SceneBuild metadata or scene properties."""
    if hasattr(sb, "qtype") and sb.qtype:
        return sb.qtype.upper()  # type: ignore[return-value]

    sid = sb.scene.scene_id.upper()
    for candidate in ("DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"):
        if f"_{candidate}_" in sid or sid.endswith(f"_{candidate}"):
            return candidate  # type: ignore[return-value]

    # Topology heuristics
    entry_dest_ids = {e.dest_id for e in sb.scene.entries}
    if sb.target_dest_id not in entry_dest_ids:
        return "ABSENT"
    if any(e.source == "temporary_notice" for e in sb.scene.entries):
        return "OVERRIDE"
    if any(e.status == "closed" for e in sb.scene.entries):
        return "CLOSURE"

    return "DIRECT"


def format_question(
    qtype: str,
    dest_name: str,
    turn_phrase: str | None = None,
) -> str:
    """Format question text using standardized phrasing templates.

    Args:
        qtype: Benchmark question type.
        dest_name: English label of the target destination.
        turn_phrase: Turn description for EGOCENTRIC questions.

    Returns:
        Formatted question prompt string.
    """
    q = qtype.upper()
    if q == "DIRECT":
        return f"You are standing in front of this signboard. Which way should you go to reach {dest_name}?"
    elif q == "BINDING":
        return (
            f"You are standing in front of this signboard. Which way should you go to reach {dest_name}? "
            f"Several signs are stacked; use only the arrow that belongs to {dest_name}."
        )
    elif q == "CLOSURE":
        return (
            f"Can you reach {dest_name} by the route shown? "
            f"If the route is closed answer CLOSED, otherwise give the direction."
        )
    elif q == "OVERRIDE":
        return f"Follow the instructions that are currently valid. Which way should you go to reach {dest_name}?"
    elif q == "EGOCENTRIC":
        phrase = turn_phrase or "turn around (180 degrees)"
        return (
            f"First work out which way {dest_name} is from this board. "
            f"Then you {phrase}. Which way is {dest_name} relative to you now?"
        )
    elif q == "ABSENT":
        return (
            f"Does this board show a way to {dest_name}? "
            f"If it does, give the direction; if the board does not mention it, answer NOT_INDICATED."
        )
    else:
        raise ValueError(f"Unknown question type: {qtype}")


def make_task(
    sb: SceneBuild,
    venue: Venue,
    rng: np.random.Generator,
    task_id: str,
    seed: int,
    image_path: str,
    scene_path: str,
) -> Task:
    """Construct a complete benchmark Task specification from a SceneBuild.

    The gold answer is derived purely from the graph solver (never from scene
    entries or model predictions).

    Args:
        sb: Populated SceneBuild instance.
        venue: Physical venue layout topology.
        rng: Seeded random generator.
        task_id: Unique task identifier.
        seed: Task random seed.
        image_path: Relative path to rendered signboard image.
        scene_path: Relative path to serialized scene specification.

    Returns:
        Task instance with gold reference, question, options, and difficulty profile.
    """
    qtype = _infer_qtype(sb)

    # Destination node lookup for English label
    target_node = next(n for n in venue.nodes if n.id == sb.target_dest_id)
    dest_name = target_node.label.en

    turn_cw: int | None = None
    turn_phrase: str | None = None

    if qtype == "EGOCENTRIC":
        turn_idx = int(rng.integers(0, len(EGOCENTRIC_TURNS)))
        turn_cw, turn_phrase = EGOCENTRIC_TURNS[turn_idx]

    question = format_question(qtype, dest_name, turn_phrase)

    # Derive reference gold answer solely from the venue graph solver
    is_listed = qtype != "ABSENT"
    gold: Answer = gold_answer(
        venue=venue,
        closed_edges=sb.scene.closed_edges,
        junction=sb.scene.junction_id,
        heading=sb.scene.heading,
        dest=sb.target_dest_id,
        turn_cw=turn_cw,
        listed=is_listed,
    )

    # Skill tags
    skill_tags = list(BASE_SKILL_TAGS.get(qtype, ["arrow_reading"]))
    if len(sb.scene.knobs.scripts) > 1 and "multi_script" not in skill_tags:
        skill_tags.append("multi_script")

    # Difficulty dictionary from difficulty knobs
    difficulty = {
        "n_entries": sb.scene.knobs.n_entries,
        "perspective_deg": sb.scene.knobs.perspective_deg,
        "blur": sb.scene.knobs.blur,
        "noise": sb.scene.knobs.noise,
        "lighting": sb.scene.knobs.lighting,
        "clutter": sb.scene.knobs.clutter,
        "occlusion": sb.scene.knobs.occlusion,
        "jpeg_quality": sb.scene.knobs.jpeg_quality,
        "template": sb.scene.knobs.template,
    }

    # Initial receipt (verified later by independent verifier)
    receipt = Receipt(
        solver_answer=gold,
        independent_answer=gold,
        agree=True,
        fidelity_ok=False,
        visibility_ok=False,
        evidence_visible_ratio=1.0,
        human_audit="unaudited",
        notes="pre-verification",
    )

    return Task(
        task_id=task_id,
        schema_version="1.0.0",
        generator_version="1.0.0",
        seed=seed,
        qtype=qtype,
        question=question,
        options=list(ANSWER_OPTIONS),
        gold=gold,
        image_path=image_path,
        scene_path=scene_path,
        target_dest_id=sb.target_dest_id,
        turn_cw=turn_cw,
        skill_tags=skill_tags,
        difficulty=difficulty,
        receipt=receipt,
    )


__all__ = [
    "EGOCENTRIC_TURNS",
    "format_question",
    "make_task",
    "options_for_task",
]
