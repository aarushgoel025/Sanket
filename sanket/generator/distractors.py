"""Distractor generator for realistic signage environments.

Injects visual and informational noise such as advertisements,
unrelated icons, regulatory notices, and platform/gate numbers
positioned deterministically in non-evidence zones.
"""

from typing import Literal

import numpy as np

from sanket.schema import Distractor

DistractorKind = Literal["ad", "icon", "number", "text"]

ADS_POOL = [
    "Chai & Snacks - Platform 1",
    "Sanket Water - 100% Pure & Safe",
    "City Transit Card - Tap & Go",
    "Fast Track Courier Service",
    "Metro Cafe - Fresh Coffee & Tea",
    "Kashi Souvenirs & Book Depot",
    "City Health Checkup - 20% Off",
    "Express Luggage Cloakroom",
]

ICONS_POOL = [
    "wifi",
    "no_smoking",
    "cctv_in_operation",
    "drinking_water",
    "dustbin",
    "first_aid",
    "fire_extinguisher",
    "escalator",
]

NUMBERS_POOL = [
    "Helpline: 139",
    "Emergency: 112",
    "Sign ID: #402",
    "Zone 4B",
    "Bay 07",
    "Pillar 14",
    "Terminal 2",
    "Gate 18",
]

TEXTS_POOL = [
    "Mind the gap",
    "Keep premises clean",
    "Silence zone",
    "Beware of pickpockets",
    "Queue here",
    "Authorized personnel only",
    "Do not lean against glass",
    "Luggage inspection mandatory",
]

CONTENT_POOLS: dict[DistractorKind, list[str]] = {
    "ad": ADS_POOL,
    "icon": ICONS_POOL,
    "number": NUMBERS_POOL,
    "text": TEXTS_POOL,
}

TEMPLATE_NON_EVIDENCE_ZONES: dict[str, list[tuple[float, float]]] = {
    "board_list": [
        (0.08, 0.04),
        (0.20, 0.04),
        (0.32, 0.04),
        (0.44, 0.04),
        (0.56, 0.04),
        (0.68, 0.04),
        (0.80, 0.04),
        (0.92, 0.04),
    ],
    "board_grid": [
        (0.08, 0.04),
        (0.20, 0.04),
        (0.32, 0.04),
        (0.44, 0.04),
        (0.56, 0.04),
        (0.68, 0.04),
        (0.80, 0.04),
        (0.92, 0.04),
    ],
    "board_gantry": [
        (0.10, 0.92),
        (0.22, 0.92),
        (0.35, 0.92),
        (0.48, 0.92),
        (0.60, 0.92),
        (0.72, 0.92),
        (0.84, 0.92),
        (0.94, 0.92),
    ],
}

DEFAULT_ZONES: list[tuple[float, float]] = [
    (0.10, 0.08),
    (0.50, 0.08),
    (0.90, 0.08),
    (0.10, 0.92),
    (0.50, 0.92),
    (0.90, 0.92),
]


def generate_distractors(count: int, template: str, rng: np.random.Generator) -> list[Distractor]:
    """Deterministically generate distractors positioned in non-evidence zones.

    Args:
        count: Number of distractors to generate (knobs.clutter).
        template: Board layout template name.
        rng: Seeded numpy random generator.

    Returns:
        List of generated Distractor objects.
    """
    if count <= 0:
        return []

    candidate_zones = TEMPLATE_NON_EVIDENCE_ZONES.get(template, DEFAULT_ZONES)
    # Permute candidate zones deterministically
    n_zones = len(candidate_zones)
    chosen_indices = rng.choice(n_zones, size=min(count, n_zones), replace=False)

    kinds: list[DistractorKind] = ["ad", "icon", "number", "text"]
    distractors: list[Distractor] = []

    for i in range(count):
        pos_idx = chosen_indices[i % n_zones]
        base_pos = candidate_zones[pos_idx]
        kind = str(rng.choice(kinds))
        assert kind in ("ad", "icon", "number", "text")
        pool = CONTENT_POOLS[kind]  # type: ignore[index]
        content = str(rng.choice(pool))

        distractors.append(
            Distractor(
                id=f"distractor_{i + 1}",
                kind=kind,  # type: ignore[arg-type]
                content=content,
                position=base_pos,
            )
        )

    return distractors
