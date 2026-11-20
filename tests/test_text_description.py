"""Unit tests for textual scene descriptions.

Verifies deterministic structured text generation and strict absence of gold answers
and question prompts.
"""

from pathlib import Path

import numpy as np
import pytest

from sanket.generator.scene_builder import build_scene, sample_knobs
from sanket.generator.text_description import describe_scene
from sanket.graph.venue import load_venue
from sanket.questions.options import ANSWER_OPTIONS
from sanket.questions.templates import make_task
from sanket.schema import Venue

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


@pytest.mark.parametrize("qtype", QUESTION_TYPES)
def test_describe_scene_no_leakage_and_valid_structure(station_venue: Venue, qtype: str) -> None:
    """Verify describe_scene output contains no gold declaration and no question text."""
    rng = np.random.default_rng(700)
    knobs = sample_knobs(rng, qtype)
    sb = build_scene(station_venue, qtype, rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id=f"test_leak_{qtype}",
        seed=700,
        image_path="test.png",
        scene_path="test.json",
    )

    desc = describe_scene(sb.scene, station_venue)

    # 1. No question text leakage
    assert "Which way should you go" not in desc
    assert "You are standing" not in desc
    assert "Can you reach" not in desc
    assert "Follow the instructions" not in desc
    assert "Does this board show" not in desc
    assert "First work out which way" not in desc
    assert task.question not in desc

    # 2. No explicit gold label leakage (e.g. "Gold: ...", "Answer: ...", "Correct: ...")
    assert "gold" not in desc.lower()
    assert "answer:" not in desc.lower()
    assert "correct:" not in desc.lower()

    # 3. Uses canonical octant arrow words
    valid_arrow_words = set(ANSWER_OPTIONS) - {"CLOSED", "NOT_INDICATED"}
    desc_tokens = {w.strip(",.;:()") for w in desc.split()}
    assert any(w in desc_tokens for w in valid_arrow_words)

    # 4. Each entry line contains status and arrow
    for line in desc.strip().splitlines()[1:]:
        assert "arrow " in line
        assert "status " in line


def test_describe_scene_determinism(hospital_venue: Venue) -> None:
    """Verify describe_scene produces identical text for identical Scene specification."""
    rng = np.random.default_rng(888)
    knobs = sample_knobs(rng, "OVERRIDE")
    sb1 = build_scene(hospital_venue, "OVERRIDE", np.random.default_rng(888), knobs)
    sb2 = build_scene(hospital_venue, "OVERRIDE", np.random.default_rng(888), knobs)

    desc1 = describe_scene(sb1.scene, hospital_venue)
    desc2 = describe_scene(sb2.scene, hospital_venue)

    assert desc1 == desc2
    assert "Temporary notice (yellow panel):" in desc1
