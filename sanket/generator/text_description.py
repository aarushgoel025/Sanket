"""Textual scene description generator for text-only baseline evaluation.

Converts a Scene specification into structured, deterministic textual representations
for evaluating language models without vision inputs.
"""

from sanket.graph.orientation import to_octant
from sanket.schema import Scene, Venue


def describe_scene(scene: Scene, venue: Venue) -> str:
    """Generate structured plain-text description of a signage scene.

    Lists each permanent entry and temporary notice with its label, canonical arrow word,
    operational status, and source.

    Args:
        scene: Scene specification model.
        venue: Physical venue layout model.

    Returns:
        Structured text description.
    """
    lines: list[str] = [f"Signboard at {venue.name} (layout: {scene.knobs.template}):"]

    permanent_idx = 1
    for entry in scene.entries:
        arrow_word = to_octant(entry.arrow_angle)

        label_parts = [entry.label.en]
        if entry.label.hi:
            label_parts.append(f"(Hindi: {entry.label.hi})")
        if entry.label.regional:
            label_parts.append(f"(Regional: {entry.label.regional})")
        label_str = " ".join(label_parts)

        if entry.source == "temporary_notice":
            lines.append(
                f"Temporary notice (yellow panel): {label_str}, arrow {arrow_word}, status {entry.status}."
            )
        else:
            lines.append(
                f"Entry {permanent_idx}: {label_str}, arrow {arrow_word}, status {entry.status}."
            )
            permanent_idx += 1

    return "\n".join(lines)


__all__ = ["describe_scene"]
