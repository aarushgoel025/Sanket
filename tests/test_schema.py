"""Tests for Sanket schema validation, venue loader, and configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from sanket.config import DefaultConfig, ModelsConfig, load_default_config, load_models_config
from sanket.graph.venue import load_venue
from sanket.schema import (
    ANSWER_OPTIONS,
    OCTANTS,
    BoardEntry,
    Edge,
    Knobs,
    Label,
    Node,
    Receipt,
    Scene,
    Task,
    Venue,
)


def test_valid_venues_load() -> None:
    """Verify that both venue YAML files load and validate without error."""
    railway = load_venue("config/venues/railway_station.yaml")
    assert isinstance(railway, Venue)
    assert railway.id == "railway_station"
    assert railway.name == "Central Junction Station"
    assert railway.kind == "railway"

    # Check junctions >= 4, destinations >= 10
    junctions = [n for n in railway.nodes if n.kind == "junction"]
    destinations = [n for n in railway.nodes if n.kind == "destination"]
    assert len(junctions) >= 4
    assert len(destinations) >= 10

    # Every destination must have en and hi
    for d in destinations:
        assert d.label.en and d.label.en.strip()
        assert d.label.hi and d.label.hi.strip()

    hospital = load_venue("config/venues/hospital.yaml")
    assert isinstance(hospital, Venue)
    assert hospital.id == "hospital"
    assert hospital.name == "City General Hospital"
    assert hospital.kind == "hospital"

    h_junctions = [n for n in hospital.nodes if n.kind == "junction"]
    h_destinations = [n for n in hospital.nodes if n.kind == "destination"]
    assert len(h_junctions) >= 3
    assert len(h_destinations) >= 9

    for d in h_destinations:
        assert d.label.en and d.label.en.strip()
        assert d.label.hi and d.label.hi.strip()


def test_bearing_not_multiple_of_45_rejected() -> None:
    """Bearings that are not multiples of 45 in [0, 315] must be rejected."""
    # Valid bearings
    for b in (0, 45, 90, 135, 180, 225, 270, 315):
        edge = Edge(a="j1", b="j2", bearing_ab=b, length=10.0)
        assert edge.bearing_ab == b

    # Invalid bearings in Edge
    for invalid in (30, 50, 75, 360, -45, 100):
        with pytest.raises(ValidationError):
            Edge(a="j1", b="j2", bearing_ab=invalid, length=10.0)  # type: ignore[arg-type]

    # Invalid bearing in BoardEntry
    with pytest.raises(ValidationError):
        BoardEntry(
            dest_id="d1",
            label=Label(en="Exit", hi="निकास"),
            arrow_angle=30,  # type: ignore[arg-type]
        )

    # Invalid heading in Scene
    with pytest.raises(ValidationError):
        Scene(
            scene_id="s1",
            venue_id="v1",
            junction_id="j1",
            heading=50,  # type: ignore[arg-type]
            entries=[],
            knobs=Knobs(
                n_entries=3,
                scripts=["en"],
                perspective_deg=0.0,
                blur=0.0,
                noise=0.0,
                lighting=1.0,
                clutter=0,
                occlusion=0.0,
                jpeg_quality=95,
                template="board_list.html.j2",
            ),
        )


def test_unknown_edge_endpoint_rejected() -> None:
    """Edges referencing nodes not in venue.nodes must be rejected."""
    node1 = Node(id="j1", kind="junction", label=Label(en="Junction 1"))
    node2 = Node(id="d1", kind="destination", label=Label(en="Exit", hi="निकास"))

    # Endpoint 'j_unknown' does not exist
    edge_bad_a = Edge(a="j_unknown", b="d1", bearing_ab=90, length=10.0)
    with pytest.raises(ValidationError, match="does not exist in venue nodes"):
        Venue(
            id="v_test",
            name="Test Venue",
            kind="railway",
            nodes=[node1, node2],
            edges=[edge_bad_a],
        )

    # Endpoint 'd_unknown' does not exist
    edge_bad_b = Edge(a="j1", b="d_unknown", bearing_ab=90, length=10.0)
    with pytest.raises(ValidationError, match="does not exist in venue nodes"):
        Venue(
            id="v_test",
            name="Test Venue",
            kind="railway",
            nodes=[node1, node2],
            edges=[edge_bad_b],
        )


def test_missing_hindi_label_on_destination_rejected() -> None:
    """Destination nodes must have both English and Hindi labels."""
    # Destination with missing Hindi (None)
    with pytest.raises(ValidationError, match="non-empty Hindi label"):
        Node(id="d1", kind="destination", label=Label(en="Platform 1", hi=None))

    # Destination with empty Hindi
    with pytest.raises(ValidationError, match="non-empty Hindi label"):
        Node(id="d1", kind="destination", label=Label(en="Platform 1", hi="   "))

    # Destination with missing English
    with pytest.raises(ValidationError, match="non-empty English label"):
        Node(id="d1", kind="destination", label=Label(en="", hi="प्लेटफ़ॉर्म 1"))

    # Junction nodes do NOT require Hindi
    junction = Node(id="j1", kind="junction", label=Label(en="Concourse"))
    assert junction.label.hi is None


def test_disconnected_venue_rejected() -> None:
    """Venues where the graph is disconnected when all edges are open must be rejected."""
    n1 = Node(id="j1", kind="junction", label=Label(en="J1"))
    n2 = Node(id="d1", kind="destination", label=Label(en="D1", hi="डी1"))
    n3 = Node(id="j2", kind="junction", label=Label(en="J2"))
    n4 = Node(id="d2", kind="destination", label=Label(en="D2", hi="डी2"))

    # Component 1: j1 - d1; Component 2: j2 - d2 (isolated from Component 1)
    e1 = Edge(a="j1", b="d1", bearing_ab=0, length=10.0)
    e2 = Edge(a="j2", b="d2", bearing_ab=0, length=10.0)

    with pytest.raises(ValidationError, match="disconnected"):
        Venue(
            id="v_disconn",
            name="Disconnected Venue",
            kind="hospital",
            nodes=[n1, n2, n3, n4],
            edges=[e1, e2],
        )


def test_duplicate_node_ids_rejected() -> None:
    """Venue with duplicate node IDs must be rejected."""
    n1 = Node(id="j1", kind="junction", label=Label(en="J1"))
    n2 = Node(id="j1", kind="destination", label=Label(en="Duplicate", hi="डुप्लिकेट"))
    e = Edge(a="j1", b="j1", bearing_ab=0, length=5.0)

    with pytest.raises(ValidationError, match="Duplicate node id"):
        Venue(
            id="v_dup",
            name="Duplicate Venue",
            kind="hospital",
            nodes=[n1, n2],
            edges=[e],
        )


def test_answer_options_contract() -> None:
    """ANSWER_OPTIONS must match fixed 10-option set in exact contract order."""
    expected = [
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
    assert ANSWER_OPTIONS == expected
    assert OCTANTS == expected[:8]


def test_scene_closed_edges_field() -> None:
    """Scene model must accept closed_edges with default []."""
    knobs = Knobs(
        n_entries=2,
        scripts=["en"],
        perspective_deg=0.0,
        blur=0.0,
        noise=0.0,
        lighting=1.0,
        clutter=0,
        occlusion=0.0,
        jpeg_quality=95,
        template="board_list.html.j2",
    )
    scene = Scene(
        scene_id="s1",
        venue_id="railway_station",
        junction_id="j_concourse",
        heading=0,
        entries=[],
        knobs=knobs,
    )
    assert scene.closed_edges == []

    scene_closed = Scene(
        scene_id="s2",
        venue_id="railway_station",
        junction_id="j_concourse",
        heading=90,
        entries=[],
        knobs=knobs,
        closed_edges=[("j_concourse", "j_exit_hall")],
    )
    assert scene_closed.closed_edges == [("j_concourse", "j_exit_hall")]


def test_task_receipt_models() -> None:
    """Verify Task and Receipt instantiation."""
    receipt = Receipt(
        solver_answer="AHEAD",
        independent_answer="AHEAD",
        agree=True,
        fidelity_ok=True,
        visibility_ok=True,
        evidence_visible_ratio=1.0,
    )
    task = Task(
        task_id="t1",
        schema_version="v1",
        generator_version="v1",
        seed=1234,
        qtype="DIRECT",
        question="Which direction to Platform 1?",
        options=ANSWER_OPTIONS,
        gold="AHEAD",
        image_path="images/t1.png",
        scene_path="scenes/t1.json",
        target_dest_id="d_p1",
        receipt=receipt,
    )
    assert task.gold == "AHEAD"
    assert task.qtype == "DIRECT"
    assert task.receipt.agree is True


def test_config_loaders(tmp_path: Path) -> None:
    """Verify default and models config loading and validation error on missing keys."""
    default_cfg = load_default_config()
    assert isinstance(default_cfg, DefaultConfig)
    assert default_cfg.master_seed == 1234
    assert default_cfg.total_tasks == 500
    assert default_cfg.keep_tasks == 400
    assert default_cfg.quotas.DIRECT == 83
    assert default_cfg.quotas.ABSENT == 83

    models_cfg = load_models_config()
    assert isinstance(models_cfg, ModelsConfig)
    assert len(models_cfg.models) >= 2
    assert models_cfg.blind_model == "gemini_flash"

    # Test missing keys in default config raises ValueError with clear message
    bad_cfg_file = tmp_path / "bad_config.yaml"
    bad_cfg_file.write_text("master_seed: 1234\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required configuration key"):
        load_default_config(bad_cfg_file)


def test_load_venue_file_not_found() -> None:
    """Non-existent venue path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_venue("config/venues/non_existent.yaml")
