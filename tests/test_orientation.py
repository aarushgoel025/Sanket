"""Unit tests for orientation and bearing calculation [HUMAN-OWNED].

Tests relative bearings, viewer octant mapping, wrap-around semantics,
and egocentric turns.
"""

import pytest

from sanket.graph.orientation import (
    apply_turn,
    norm,
    relative_bearing,
    to_octant,
)

ORIENTATION_CASES = [
    # Heading 0
    (0, 0, "AHEAD"),
    (45, 0, "AHEAD_RIGHT"),
    (90, 0, "RIGHT"),
    (135, 0, "BACK_RIGHT"),
    (180, 0, "BACK"),
    (225, 0, "BACK_LEFT"),
    (270, 0, "LEFT"),
    (315, 0, "AHEAD_LEFT"),
    # Heading 45
    (0, 45, "AHEAD_LEFT"),
    (45, 45, "AHEAD"),
    (90, 45, "AHEAD_RIGHT"),
    (135, 45, "RIGHT"),
    (180, 45, "BACK_RIGHT"),
    (225, 45, "BACK"),
    (270, 45, "BACK_LEFT"),
    (315, 45, "LEFT"),
    # Heading 90
    (0, 90, "LEFT"),
    (45, 90, "AHEAD_LEFT"),
    (90, 90, "AHEAD"),
    (135, 90, "AHEAD_RIGHT"),
    (180, 90, "RIGHT"),
    (225, 90, "BACK_RIGHT"),
    (270, 90, "BACK"),
    (315, 90, "BACK_LEFT"),
    # Heading 180
    (0, 180, "BACK"),
    (45, 180, "BACK_LEFT"),
    (90, 180, "LEFT"),
    (135, 180, "AHEAD_LEFT"),
    (180, 180, "AHEAD"),
    (225, 180, "AHEAD_RIGHT"),
    (270, 180, "RIGHT"),
    (315, 180, "BACK_RIGHT"),
    # Heading 270 (wrap-arounds)
    (0, 270, "RIGHT"),
    (45, 270, "BACK_RIGHT"),
    (90, 270, "BACK"),
    (135, 270, "BACK_LEFT"),
    (180, 270, "LEFT"),
    (225, 270, "AHEAD_LEFT"),
    (270, 270, "AHEAD"),
    (315, 270, "AHEAD_RIGHT"),
    # Additional wrap-around combinations
    (270, 90, "BACK"),
    (45, 315, "RIGHT"),
    (315, 45, "LEFT"),
    (45, 270, "BACK_RIGHT"),
]


@pytest.mark.parametrize(("target", "heading", "expected"), ORIENTATION_CASES)
def test_relative_bearing_and_octant(target: int, heading: int, expected: str) -> None:
    """Verify that (target, heading) resolves to the expected octant."""
    rel = relative_bearing(target, heading)
    assert to_octant(rel) == expected


TURN_CASES = [
    (0, 180, "BACK"),
    (0, 90, "LEFT"),
    (90, 90, "AHEAD"),
    (180, 270, "LEFT"),
    (0, 0, "AHEAD"),
    (90, 180, "LEFT"),
    (270, 90, "BACK"),
    (45, 90, "AHEAD_LEFT"),
]


@pytest.mark.parametrize(("rel", "turn_cw", "expected"), TURN_CASES)
def test_apply_turn(rel: int, turn_cw: int, expected: str) -> None:
    """Verify clockwise viewer turns transform relative bearings correctly."""
    turned = apply_turn(rel, turn_cw)
    assert to_octant(turned) == expected


def test_norm() -> None:
    """Test angle normalization across 360-degree boundaries."""
    assert norm(0) == 0
    assert norm(360) == 0
    assert norm(720) == 0
    assert norm(-45) == 315
    assert norm(-90) == 270
    assert norm(405) == 45


@pytest.mark.parametrize("invalid_deg", [1, 15, 30, 44, 46, 89, 91, 100, 200, 359])
def test_non_multiple_of_45_raises_assertion_error(invalid_deg: int) -> None:
    """Verify to_octant asserts that input bearing is a multiple of 45."""
    with pytest.raises(AssertionError, match="bearings must be multiples of 45"):
        to_octant(invalid_deg)
