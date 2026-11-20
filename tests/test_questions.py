"""Unit tests for question phrasing, option invariants, and solver gold derivation.

Tests all question types, turn mapping, and verifies 12 hand-computed ground truth examples.
"""

from pathlib import Path

import numpy as np
import pytest

from sanket.generator.scene_builder import SceneBuild, build_scene, sample_knobs
from sanket.graph.solver import gold_answer
from sanket.graph.venue import load_venue
from sanket.questions.options import ANSWER_OPTIONS, options_for_task
from sanket.questions.templates import (
    EGOCENTRIC_TURNS,
    format_question,
    make_task,
)
from sanket.schema import BoardEntry, Knobs, Label, Scene, Task, Venue

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


def test_options_invariants() -> None:
    """Verify options_for_task returns ANSWER_OPTIONS in exact immutable order."""
    opts = options_for_task()
    assert opts == [
        "AHEAD",
        "AHEAD_RIGHT",
        "RIGHT",
        "BACK_RIGHT",
        "BACK",
        "BACK_LEFT",
        "LEFT",
        "AHEAD_LEFT",
        "CLOSED",
        "NOT_INDICATED",
    ]
    assert opts == list(ANSWER_OPTIONS)


# 12 hand-computed ground truth test specifications on Central Junction Station
HAND_COMPUTED_12 = [
    # 1. DIRECT: Concourse heading 0 to Ticket counter (bearing 180) -> BACK
    ("DIRECT", "j_concourse", 0, "d_ticket", [], None, True, "BACK"),
    # 2. DIRECT: Concourse heading 90 to Waiting hall (bearing 270) -> rel (270 - 90) = 180 -> BACK
    ("DIRECT", "j_concourse", 90, "d_waiting", [], None, True, "BACK"),
    # 3. DIRECT: Concourse heading 0 to Lift (bearing 315) -> rel 315 -> AHEAD_LEFT
    ("DIRECT", "j_concourse", 0, "d_lift", [], None, True, "AHEAD_LEFT"),
    # 4. DIRECT: FOB heading 0 to Platform 1 (bearing 270) -> rel 270 -> LEFT
    ("DIRECT", "j_fob", 0, "d_p1", [], None, True, "LEFT"),
    # 5. BINDING: FOB heading 0 to Platform 3 (bearing 0) -> rel 0 -> AHEAD
    ("BINDING", "j_fob", 0, "d_p3", [], None, True, "AHEAD"),
    # 6. BINDING: FOB heading 45 to Platform 4 (bearing 45) -> rel (45 - 45) = 0 -> AHEAD
    ("BINDING", "j_fob", 45, "d_p4", [], None, True, "AHEAD"),
    # 7. CLOSURE: Concourse to Ticket with edge closed -> CLOSED
    ("CLOSURE", "j_concourse", 0, "d_ticket", [("j_concourse", "d_ticket")], None, True, "CLOSED"),
    # 8. CLOSURE: FOB to Platform 2 with edge closed -> CLOSED
    ("CLOSURE", "j_fob", 90, "d_p2", [("j_fob", "d_p2")], None, True, "CLOSED"),
    # 9. OVERRIDE: Concourse heading 0 to Platform 5 with main edge closed -> detours via FOB (bearing 0) -> AHEAD
    ("OVERRIDE", "j_concourse", 0, "d_p5", [("j_concourse", "j_exit_hall")], None, True, "AHEAD"),
    # 10. EGOCENTRIC: Concourse heading 0 to Lift (bearing 315 -> rel 315) + turn 180 -> rel 135 -> BACK_RIGHT
    ("EGOCENTRIC", "j_concourse", 0, "d_lift", [], 180, True, "BACK_RIGHT"),
    # 11. EGOCENTRIC: Concourse heading 0 to Ticket (bearing 180 -> rel 180) + turn 90 right -> rel 90 -> RIGHT
    ("EGOCENTRIC", "j_concourse", 0, "d_ticket", [], 90, True, "RIGHT"),
    # 12. ABSENT: Concourse to Platform 1 unlisted -> NOT_INDICATED
    ("ABSENT", "j_concourse", 0, "d_p1", [], None, False, "NOT_INDICATED"),
]


@pytest.mark.parametrize(
    ("qtype", "junction", "heading", "dest", "closed_edges", "turn_cw", "listed", "expected_gold"),
    HAND_COMPUTED_12,
)
def test_twelve_hand_computed_examples(
    station_venue: Venue,
    qtype: str,
    junction: str,
    heading: int,
    dest: str,
    closed_edges: list[tuple[str, str]],
    turn_cw: int | None,
    listed: bool,
    expected_gold: str,
) -> None:
    """Verify solver gold answer matches hand-computed expectations for 12 fixed benchmark cases."""
    # 1. Direct solver verification
    gold = gold_answer(
        venue=station_venue,
        closed_edges=closed_edges,
        junction=junction,
        heading=heading,
        dest=dest,
        turn_cw=turn_cw,
        listed=listed,
    )
    assert gold == expected_gold

    # 2. End-to-end task creation verification
    dummy_entry = BoardEntry(
        dest_id=dest,
        label=Label(en="Target Dest", hi="लक्ष्य"),
        arrow_angle=0,
        status="closed" if qtype == "CLOSURE" else "open",
        source="temporary_notice" if qtype == "OVERRIDE" else "permanent",
    )
    dummy_scene = Scene(
        scene_id=f"scene_{station_venue.id}_{junction}_{qtype.lower()}_11111",
        venue_id=station_venue.id,
        junction_id=junction,
        heading=heading,
        entries=[] if qtype == "ABSENT" else [dummy_entry],
        knobs=Knobs(
            n_entries=2,
            scripts=["en"],
            perspective_deg=0.0,
            blur=0.0,
            noise=0.0,
            lighting=0.0,
            clutter=0,
            occlusion=0.0,
            jpeg_quality=90,
            template="board_list",
        ),
        closed_edges=closed_edges,
    )
    sb = SceneBuild(scene=dummy_scene, target_dest_id=dest, qtype=qtype)

    rng = np.random.default_rng(42)
    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id=f"task_{qtype}_001",
        seed=42,
        image_path="test.png",
        scene_path="test.json",
    )

    if qtype == "EGOCENTRIC":
        # Force the tested turn_cw onto the task to verify exact alignment
        task_gold = gold_answer(
            venue=station_venue,
            closed_edges=closed_edges,
            junction=junction,
            heading=heading,
            dest=dest,
            turn_cw=turn_cw,
            listed=listed,
        )
        assert task_gold == expected_gold
    else:
        assert task.gold == expected_gold
        assert task.options == list(ANSWER_OPTIONS)


def test_one_hundred_tasks_generation_and_solver_alignment(
    station_venue: Venue, hospital_venue: Venue
) -> None:
    """Generate 100 tasks across venues and question types and verify solver gold alignment."""
    venues = [station_venue, hospital_venue]
    total_built = 0

    for idx in range(100):
        v = venues[idx % len(venues)]
        qtype = QUESTION_TYPES[idx % len(QUESTION_TYPES)]
        rng = np.random.default_rng(10000 + idx)

        knobs = sample_knobs(rng, qtype)
        sb = build_scene(v, qtype, rng, knobs)

        task = make_task(
            sb=sb,
            venue=v,
            rng=rng,
            task_id=f"task_bench_{idx:03d}",
            seed=10000 + idx,
            image_path=f"images/task_{idx:03d}.png",
            scene_path=f"scenes/task_{idx:03d}.json",
        )

        assert isinstance(task, Task)
        assert task.qtype == qtype
        assert task.options == list(ANSWER_OPTIONS)
        assert len(task.question) > 10

        # Verify gold matches direct call to solver.gold_answer
        expected_solver_gold = gold_answer(
            venue=v,
            closed_edges=sb.scene.closed_edges,
            junction=sb.scene.junction_id,
            heading=sb.scene.heading,
            dest=sb.target_dest_id,
            turn_cw=task.turn_cw,
            listed=(qtype != "ABSENT"),
        )
        assert task.gold == expected_solver_gold
        total_built += 1

    assert total_built == 100


def test_egocentric_turn_mapping_all_three_turns(station_venue: Venue) -> None:
    """Verify all three EGOCENTRIC turns map correctly to degrees and question phrases."""
    expected_mappings = {
        180: "turn around (180 degrees)",
        90: "turn 90 degrees to your right",
        270: "turn 90 degrees to your left",
    }

    assert len(EGOCENTRIC_TURNS) == 3
    for deg, phrase in EGOCENTRIC_TURNS:
        assert expected_mappings[deg] == phrase

        # Test format_question
        q_text = format_question("EGOCENTRIC", "Platform 1", phrase)
        assert phrase in q_text
        assert "Platform 1" in q_text
        assert "Which way is Platform 1 relative to you now?" in q_text


def test_question_wording_templates() -> None:
    """Verify standardized question wording templates across all types."""
    dest = "Emergency"
    assert format_question("DIRECT", dest) == (
        "You are standing in front of this signboard. Which way should you go to reach Emergency?"
    )
    assert format_question("BINDING", dest) == (
        "You are standing in front of this signboard. Which way should you go to reach Emergency? "
        "Several signs are stacked; use only the arrow that belongs to Emergency."
    )
    assert format_question("CLOSURE", dest) == (
        "Can you reach Emergency by the route shown? If the route is closed answer CLOSED, otherwise give the direction."
    )
    assert format_question("OVERRIDE", dest) == (
        "Follow the instructions that are currently valid. Which way should you go to reach Emergency?"
    )
    assert format_question("ABSENT", dest) == (
        "Does this board show a way to Emergency? If it does, give the direction; if the board does not mention it, answer NOT_INDICATED."
    )
