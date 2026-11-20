"""Visual evidence visibility and occlusion validator.

Ensures that required wayfinding evidence elements (target labels, arrows,
closed overlays, and temporary notices) are positioned inside the image viewport
and remain unoccluded (occluded_ratio <= 0.10) after augmentations.
"""

import numpy as np

from sanket.schema import ElementGeo, Geometry, Scene, Task


def _bbox_inside_image(
    bbox: tuple[float, float, float, float] | list[float],
    image_size: tuple[int, int],
) -> bool:
    """Check if bounding box lies completely within the image viewport."""
    x, y, w, h = bbox
    img_w, img_h = image_size
    # Allow 1.0px floating point tolerance at edges
    return (
        x >= -1.0
        and y >= -1.0
        and (x + w) <= (img_w + 1.0)
        and (y + h) <= (img_h + 1.0)
        and w > 0.0
        and h > 0.0
    )


def visibility_ok(
    scene: Scene,
    task: Task,
    geometry_after_augment: Geometry,
    image_size: tuple[int, int] = (1280, 720),
) -> tuple[bool, float]:
    """Verify that critical wayfinding evidence elements are visible and unoccluded.

    Evidence set:
    - For ABSENT tasks: all entry labels displayed on the board.
    - For other tasks: target label, target arrow, closed_mark (if closed),
      and temporary notice (if OVERRIDE).

    Acceptance rules:
    - Every evidence element bounding box must lie inside the image dimensions.
    - Every evidence element must have occluded_ratio <= 0.10 (at least 90% unoccluded).

    Args:
        scene: Scene specification.
        task: Benchmark task specification.
        geometry_after_augment: Exported geometry after perspective warp and augmentations.
        image_size: Viewport dimensions (width, height).

    Returns:
        Tuple of (is_visibility_valid, mean_evidence_visible_ratio).
    """
    evidence: list[ElementGeo] = []

    if task.qtype == "ABSENT":
        # In absence detection, all displayed labels are evidence that target is not listed
        evidence = [e for e in geometry_after_augment.elements if e.role == "label"]
    else:
        tid = task.target_dest_id
        target_labels = [
            e for e in geometry_after_augment.elements if e.role == "label" and e.dest_id == tid
        ]
        target_arrows = [
            e for e in geometry_after_augment.elements if e.role == "arrow" and e.dest_id == tid
        ]
        evidence.extend(target_labels)
        evidence.extend(target_arrows)

        # Closed overlay check
        target_closed = any(e.dest_id == tid and e.status == "closed" for e in scene.entries)
        if task.qtype == "CLOSURE" or target_closed:
            closed_marks = [
                e
                for e in geometry_after_augment.elements
                if e.role == "closed_mark" and e.dest_id == tid
            ]
            evidence.extend(closed_marks)

        # Temporary notice check
        if task.qtype == "OVERRIDE":
            notices = [
                e
                for e in geometry_after_augment.elements
                if e.role == "notice" and (e.dest_id == tid or e.dest_id is None)
            ]
            evidence.extend(notices)

    if not evidence:
        return False, 0.0

    all_inside = True
    all_unoccluded = True
    visible_ratios: list[float] = []

    for elem in evidence:
        inside = _bbox_inside_image(elem.bbox, image_size)
        if not inside:
            all_inside = False

        if elem.occluded_ratio > 0.10:
            all_unoccluded = False

        visible_ratios.append(max(0.0, 1.0 - elem.occluded_ratio))

    mean_vis_ratio = float(np.mean(visible_ratios)) if visible_ratios else 0.0
    is_valid = all_inside and all_unoccluded

    return is_valid, round(mean_vis_ratio, 4)


__all__ = ["visibility_ok"]
