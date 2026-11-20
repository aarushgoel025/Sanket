"""Render fidelity validator for signage scenes.

Verifies that rendered DOM geometry faithfully matches the Scene specification,
checking text presence, arrow orientations within 1 degree, closed marks,
and temporary notices.
"""

from sanket.schema import Geometry, Scene


def fidelity_ok(scene: Scene, geometry: Geometry) -> tuple[bool, str]:
    """Verify rendered DOM geometry matches the Scene specification.

    Rules checked for every entry:
    - Label text contains the English label name.
    - Arrow element exists with orientation matching arrow_angle within 1 degree.
    - A closed_mark element exists if and only if status is 'closed'.
    - A notice element exists if and only if a temporary_notice entry exists in the scene.

    Args:
        scene: Scene specification model.
        geometry: Exported DOM elements geometry.

    Returns:
        Tuple of (is_fidelity_valid, failure_reason_if_any).
    """
    if not geometry.elements:
        return False, "Geometry contains no elements"

    for entry in scene.entries:
        dest_id = entry.dest_id

        # 1. Label check
        labels = [e for e in geometry.elements if e.role == "label" and e.dest_id == dest_id]
        if not labels:
            return False, f"Missing label element for destination '{dest_id}'"

        expected_en = entry.label.en.strip().lower()
        if not any(e.text and expected_en in e.text.strip().lower() for e in labels):
            return (
                False,
                f"Label text for '{dest_id}' does not contain expected English name '{entry.label.en}'",
            )

        # 2. Arrow angle check
        matching_arrows = [
            e for e in geometry.elements if e.role == "arrow" and e.dest_id == dest_id
        ]
        if not matching_arrows:
            return False, f"Missing arrow element for destination '{dest_id}'"

        # If source is available, prefer matching source; otherwise find arrow with correct angle
        matching_arrow = None
        for a in matching_arrows:
            if a.source and entry.source and a.source == entry.source:
                matching_arrow = a
                break
        if matching_arrow is None:
            # Fallback to closest matching angle
            for a in matching_arrows:
                if a.angle is not None:
                    diff = abs(a.angle - entry.arrow_angle) % 360
                    if diff <= 1.0 or diff >= 359.0:
                        matching_arrow = a
                        break

        if matching_arrow is None or matching_arrow.angle is None:
            return (
                False,
                f"Arrow angle mismatch for '{dest_id}': expected {entry.arrow_angle}°",
            )

        diff = abs(matching_arrow.angle - entry.arrow_angle) % 360
        if not (diff <= 1.0 or diff >= 359.0):
            return (
                False,
                f"Arrow angle for '{dest_id}' differs by {diff:.1f}° (expected {entry.arrow_angle}°, got {matching_arrow.angle}°)",
            )

        # 3. Closed mark check
        closed_marks = [
            e for e in geometry.elements if e.role == "closed_mark" and e.dest_id == dest_id
        ]
        if entry.status == "closed":
            if not closed_marks:
                return (
                    False,
                    f"Closed mark missing for closed destination '{dest_id}'",
                )
        else:
            if closed_marks:
                return (
                    False,
                    f"Unexpected closed mark present for open destination '{dest_id}'",
                )

    # 4. Notice check
    has_temporary_notice = any(e.source == "temporary_notice" for e in scene.entries)
    notice_elements = [e for e in geometry.elements if e.role == "notice"]

    if has_temporary_notice and not notice_elements:
        return False, "Missing notice element for scene with temporary_notice entry"
    if not has_temporary_notice and notice_elements:
        return False, "Unexpected notice element found in scene without temporary notice"

    return True, ""


__all__ = ["fidelity_ok"]
