"""Independent ground-truth answer resolution [HUMAN-OWNED].

Derives an independent answer directly from the Scene entries and Task parameters
without importing or consulting graph/solver.py or venue layout graphs.
"""

from sanket.graph.orientation import apply_turn, to_octant
from sanket.schema import Answer, Scene, Task


def independent_answer(scene: Scene, task: Task) -> Answer:
    """Derive ground-truth answer independently using only Scene entries and Task.

    Rules:
    - If a temporary_notice entry exists for the target, use its arrow.
    - Otherwise, use the permanent entry for the target.
    - If no entry exists for the target on the board -> 'NOT_INDICATED'.
    - If the active entry has status 'closed' -> 'CLOSED'.
    - Otherwise, compute to_octant of arrow_angle, applying task.turn_cw for EGOCENTRIC.

    Args:
        scene: Rendered scene specification with displayed entries.
        task: Benchmark task with target_dest_id and optional turn_cw.

    Returns:
        Derived Answer string.
    """
    target_id = task.target_dest_id

    target_notice = None
    target_permanent = None

    for entry in scene.entries:
        if entry.dest_id == target_id:
            if entry.source == "temporary_notice":
                target_notice = entry
            elif entry.source == "permanent":
                target_permanent = entry

    # Temporary notice overrides permanent entry
    active_entry = target_notice if target_notice is not None else target_permanent

    # Absent from signboard
    if active_entry is None:
        return "NOT_INDICATED"

    # Route marked closed
    if active_entry.status == "closed":
        return "CLOSED"

    # Directional arrow reading with egocentric rotation support
    rel = active_entry.arrow_angle
    if task.turn_cw is not None:
        rel = apply_turn(rel, task.turn_cw)

    return to_octant(rel)


__all__ = ["independent_answer"]
