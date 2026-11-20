"""Orientation, bearing calculations, and viewer-relative octants [HUMAN-OWNED].

Computes clockwise relative bearings, maps angles into fixed octants,
and applies egocentric viewer turns.
"""

from typing import cast

from sanket.schema import OCTANTS, Octant


def norm(deg: float) -> int:
    """Normalize an angle in degrees to [0, 360)."""
    return int(deg) % 360


def relative_bearing(target_bearing: int, heading: int) -> int:
    """Compute clockwise relative bearing from heading to target_bearing."""
    return norm(target_bearing - heading)


def to_octant(rel: int) -> Octant:
    """Map a normalized relative bearing (multiple of 45) to an Octant name."""
    assert rel % 45 == 0, "bearings must be multiples of 45"
    return cast(Octant, OCTANTS[int(norm(rel) // 45)])


def apply_turn(rel: int, turn_cw: int) -> int:
    """Viewer turns clockwise by turn_cw degrees."""
    return norm(rel - turn_cw)
