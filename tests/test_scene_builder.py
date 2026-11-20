"""Unit tests for deterministic scene generation and distractor placement.

Tests all question types, solver alignment, determinism, and ambiguity rejection.
"""

from pathlib import Path

import numpy as np
import pytest

from sanket.generator.distractors import generate_distractors
from sanket.generator.scene_builder import (
    RejectScene,
    build_scene,
    sample_knobs,
)
from sanket.graph.orientation import to_octant
from sanket.graph.solver import gold_answer
from sanket.graph.venue import load_venue
from sanket.schema import (
    Edge,
    Label,
    Node,
    Venue,
)

STATION_PATH = Path("config/venues/railway_station.yaml")
HOSPITAL_PATH = Path("config/venues/hospital.yaml")

QUESTION_TYPES = ["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]


@pytest.fixture
def station_venue() -> Venue:
    """Fixture providing Central Junction Station venue."""
    return load_venue(STATION_PATH)


@pytest.fixture
def hospital_venue() -> Venue:
    """Fixture providing City General Hospital venue."""
    return load_venue(HOSPITAL_PATH)


@pytest.fixture
def ambiguous_venue() -> Venue:
    """Fixture providing a venue with solely ambiguous routes."""
    return Venue(
        id="always_ambiguous",
        name="Ambiguous Hub",
        kind="metro",
        nodes=[
            Node(id="j_ambig", kind="junction", label=Label(en="Junction", hi="जंक्शन")),
            Node(id="j_left", kind="junction", label=Label(en="Left Hub", hi="बायां")),
            Node(id="j_right", kind="junction", label=Label(en="Right Hub", hi="दायां")),
            Node(id="d_ambig", kind="destination", label=Label(en="Goal", hi="लक्ष्य")),
        ],
        edges=[
            Edge(a="j_ambig", b="j_left", bearing_ab=270, length=20.0, status="open"),
            Edge(a="j_left", b="d_ambig", bearing_ab=0, length=20.0, status="open"),
            Edge(a="j_ambig", b="j_right", bearing_ab=90, length=20.0, status="open"),
            Edge(a="j_right", b="d_ambig", bearing_ab=0, length=20.0, status="open"),
        ],
    )


@pytest.mark.parametrize("qtype", QUESTION_TYPES)
def test_fifty_seeds_build_or_reject(station_venue: Venue, qtype: str) -> None:
    """Verify that 50 random seeds build cleanly or raise RejectScene with a reason."""
    built_count = 0
    rejected_count = 0

    for seed in range(50):
        rng = np.random.default_rng(1000 + seed)
        knobs = sample_knobs(rng, qtype)
        try:
            build = build_scene(station_venue, qtype, rng, knobs)
            assert build.scene is not None
            assert build.target_dest_id
            built_count += 1
        except RejectScene as e:
            assert isinstance(e.reason, str) and len(e.reason) > 0
            rejected_count += 1

    # Over 50 seeds, the vast majority should successfully build
    assert built_count > 40
    assert built_count + rejected_count == 50


def test_direct_scene_solver_alignment(station_venue: Venue) -> None:
    """For DIRECT scenes, the target entry's arrow octant must equal gold_answer."""
    for seed in range(25):
        rng = np.random.default_rng(2000 + seed)
        knobs = sample_knobs(rng, "DIRECT")
        build = build_scene(station_venue, "DIRECT", rng, knobs)

        # Locate target entry
        target_entries = [e for e in build.scene.entries if e.dest_id == build.target_dest_id]
        assert len(target_entries) == 1
        target_entry = target_entries[0]

        expected_octant = gold_answer(
            venue=station_venue,
            closed_edges=build.scene.closed_edges,
            junction=build.scene.junction_id,
            heading=build.scene.heading,
            dest=build.target_dest_id,
            turn_cw=None,
            listed=True,
        )
        assert to_octant(target_entry.arrow_angle) == expected_octant


def test_closure_scene_solver_returns_closed(station_venue: Venue) -> None:
    """For CLOSURE scenes, the solver must return CLOSED for the target."""
    for seed in range(25):
        rng = np.random.default_rng(3000 + seed)
        knobs = sample_knobs(rng, "CLOSURE")
        build = build_scene(station_venue, "CLOSURE", rng, knobs)

        assert len(build.scene.closed_edges) > 0

        target_entries = [e for e in build.scene.entries if e.dest_id == build.target_dest_id]
        assert len(target_entries) == 1
        assert target_entries[0].status == "closed"

        solver_ans = gold_answer(
            venue=station_venue,
            closed_edges=build.scene.closed_edges,
            junction=build.scene.junction_id,
            heading=build.scene.heading,
            dest=build.target_dest_id,
            turn_cw=None,
            listed=True,
        )
        assert solver_ans == "CLOSED"


def test_override_scene_solver_and_notice_alignment(station_venue: Venue) -> None:
    """For OVERRIDE scenes: permanent arrow != notice arrow, and solver first hop == notice arrow."""
    for seed in range(25):
        rng = np.random.default_rng(4000 + seed)
        knobs = sample_knobs(rng, "OVERRIDE")
        build = build_scene(station_venue, "OVERRIDE", rng, knobs)

        assert len(build.scene.closed_edges) == 1

        perm_entries = [
            e
            for e in build.scene.entries
            if e.dest_id == build.target_dest_id and e.source == "permanent"
        ]
        notice_entries = [
            e
            for e in build.scene.entries
            if e.dest_id == build.target_dest_id and e.source == "temporary_notice"
        ]

        assert len(perm_entries) == 1
        assert len(notice_entries) == 1

        perm_arrow = perm_entries[0].arrow_angle
        notice_arrow = notice_entries[0].arrow_angle

        # Permanent arrow must differ from notice arrow
        assert perm_arrow != notice_arrow

        # Solver's first hop must equal the notice arrow octant
        solver_ans = gold_answer(
            venue=station_venue,
            closed_edges=build.scene.closed_edges,
            junction=build.scene.junction_id,
            heading=build.scene.heading,
            dest=build.target_dest_id,
            turn_cw=None,
            listed=True,
        )
        assert solver_ans == to_octant(notice_arrow)


def test_absent_scene_target_not_in_entries(station_venue: Venue) -> None:
    """For ABSENT scenes, the target destination must not be in board entries."""
    for seed in range(25):
        rng = np.random.default_rng(5000 + seed)
        knobs = sample_knobs(rng, "ABSENT")
        build = build_scene(station_venue, "ABSENT", rng, knobs)

        entry_dest_ids = [e.dest_id for e in build.scene.entries]
        assert build.target_dest_id not in entry_dest_ids

        # Solver should confirm NOT_INDICATED
        solver_ans = gold_answer(
            venue=station_venue,
            closed_edges=build.scene.closed_edges,
            junction=build.scene.junction_id,
            heading=build.scene.heading,
            dest=build.target_dest_id,
            turn_cw=None,
            listed=False,
        )
        assert solver_ans == "NOT_INDICATED"


def test_binding_scene_constraints(station_venue: Venue) -> None:
    """For BINDING scenes, ensure template is grid/gantry and has at least 4 entries."""
    for seed in range(25):
        rng = np.random.default_rng(6000 + seed)
        knobs = sample_knobs(rng, "BINDING")
        build = build_scene(station_venue, "BINDING", rng, knobs)

        assert build.scene.knobs.template in ("board_grid", "board_gantry")
        assert len(build.scene.entries) >= 4
        assert any(e.dest_id == build.target_dest_id for e in build.scene.entries)


def test_determinism(station_venue: Venue) -> None:
    """Verify that identical inputs and seeds generate identical Scenes."""
    for qtype in QUESTION_TYPES:
        for seed in [42, 99, 1234]:
            rng1 = np.random.default_rng(seed)
            knobs1 = sample_knobs(rng1, qtype)
            build1 = build_scene(station_venue, qtype, np.random.default_rng(seed), knobs1)

            rng2 = np.random.default_rng(seed)
            knobs2 = sample_knobs(rng2, qtype)
            build2 = build_scene(station_venue, qtype, np.random.default_rng(seed), knobs2)

            assert build1.target_dest_id == build2.target_dest_id
            assert build1.scene.model_dump() == build2.scene.model_dump()


def test_ambiguity_rejection(ambiguous_venue: Venue) -> None:
    """Verify venue with unavoidable ambiguity raises RejectScene('ambiguous_route')."""
    rng = np.random.default_rng(42)
    knobs = sample_knobs(rng, "DIRECT")
    with pytest.raises(RejectScene) as exc_info:
        build_scene(ambiguous_venue, "DIRECT", rng, knobs)
    assert exc_info.value.reason == "ambiguous_route"


def test_distractors_generation() -> None:
    """Verify seeded distractors properties and positioning."""
    rng = np.random.default_rng(777)
    distractors = generate_distractors(count=5, template="board_list", rng=rng)

    assert len(distractors) == 5
    for d in distractors:
        assert d.kind in ("ad", "icon", "number", "text")
        assert len(d.content) > 0
        assert d.position is not None
        assert 0.0 <= d.position[0] <= 1.0
        assert 0.0 <= d.position[1] <= 1.0

    # Determinism of distractors
    rng_a = np.random.default_rng(888)
    rng_b = np.random.default_rng(888)
    d_a = generate_distractors(count=4, template="board_grid", rng=rng_a)
    d_b = generate_distractors(count=4, template="board_grid", rng=rng_b)
    assert [d.model_dump() for d in d_a] == [d.model_dump() for d in d_b]
