"""Unit tests for graph solver and gold answer resolution [HUMAN-OWNED].

Tests shortest-path routing, detour resolution, closure handling,
ambiguity detection, and viewer arrow semantics.
"""

from pathlib import Path

import pytest

from sanket.graph.orientation import relative_bearing, to_octant
from sanket.graph.solver import (
    AmbiguousRoute,
    apply_closed_edges,
    build_graph,
    first_hop_bearings,
    gold_answer,
    open_subgraph,
)
from sanket.graph.venue import load_venue
from sanket.schema import (
    VALID_BEARINGS,
    Edge,
    Label,
    Node,
    Venue,
)

VENUE_PATH = Path("config/venues/railway_station.yaml")


@pytest.fixture
def station_venue() -> Venue:
    """Load Central Junction Station venue fixture."""
    return load_venue(VENUE_PATH)


@pytest.fixture
def ambiguous_venue() -> Venue:
    """Create a minimal venue with two equal-length shortest paths having distinct first hops."""
    return Venue(
        id="ambiguous_venue",
        name="Ambiguous Layout",
        kind="metro",
        nodes=[
            Node(id="j_start", kind="junction", label=Label(en="Start", hi="आरंभ")),
            Node(id="j_branch_a", kind="junction", label=Label(en="Branch A", hi="शाखा क")),
            Node(id="j_branch_b", kind="junction", label=Label(en="Branch B", hi="शाखा ख")),
            Node(id="d_goal", kind="destination", label=Label(en="Goal", hi="लक्ष्य")),
        ],
        edges=[
            Edge(a="j_start", b="j_branch_a", bearing_ab=0, length=20.0, status="open"),
            Edge(a="j_branch_a", b="d_goal", bearing_ab=90, length=20.0, status="open"),
            Edge(a="j_start", b="j_branch_b", bearing_ab=90, length=20.0, status="open"),
            Edge(a="j_branch_b", b="d_goal", bearing_ab=0, length=20.0, status="open"),
        ],
    )


def test_unique_shortest_path(station_venue: Venue) -> None:
    """Verify unique shortest path resolution for a destination from a junction."""
    # From concourse to platform end: via exit_hall (40+50=90m) vs via fob (60+70=130m)
    # First hop is to exit_hall with bearing 90. Heading 0 -> relative 90 -> RIGHT.
    ans = gold_answer(
        venue=station_venue,
        closed_edges=[],
        junction="j_concourse",
        heading=0,
        dest="j_platform_end",
        turn_cw=None,
        listed=True,
    )
    assert ans == "RIGHT"

    # From concourse to ticket counter: bearing 180. Heading 180 -> relative 0 -> AHEAD.
    ans_ticket = gold_answer(
        venue=station_venue,
        closed_edges=[],
        junction="j_concourse",
        heading=180,
        dest="d_ticket",
        turn_cw=None,
        listed=True,
    )
    assert ans_ticket == "AHEAD"


def test_closed_edge_forces_detour(station_venue: Venue) -> None:
    """Verify that closing the shortest edge forces the solver onto the alternate route."""
    # Normal shortest path to j_platform_end is via j_exit_hall (bearing 90, total 90m)
    # When (j_concourse, j_exit_hall) is closed, route detours via j_fob (bearing 0, total 130m)
    # Heading 0 -> relative bearing 0 -> AHEAD
    ans_detour = gold_answer(
        venue=station_venue,
        closed_edges=[("j_concourse", "j_exit_hall")],
        junction="j_concourse",
        heading=0,
        dest="j_platform_end",
        turn_cw=None,
        listed=True,
    )
    assert ans_detour == "AHEAD"


def test_all_edges_to_target_closed_returns_closed(station_venue: Venue) -> None:
    """Verify that when all paths to a destination are closed, gold answer is CLOSED."""
    ans = gold_answer(
        venue=station_venue,
        closed_edges=[("j_concourse", "d_ticket")],
        junction="j_concourse",
        heading=0,
        dest="d_ticket",
        turn_cw=None,
        listed=True,
    )
    assert ans == "CLOSED"


def test_not_listed_returns_not_indicated(station_venue: Venue) -> None:
    """Verify unlisted destination yields NOT_INDICATED."""
    ans = gold_answer(
        venue=station_venue,
        closed_edges=[],
        junction="j_concourse",
        heading=0,
        dest="d_ticket",
        turn_cw=None,
        listed=False,
    )
    assert ans == "NOT_INDICATED"


def test_equal_length_shortest_paths_raises_ambiguous_route(
    ambiguous_venue: Venue,
) -> None:
    """Verify equal-length shortest paths with divergent first hops raise AmbiguousRoute."""
    with pytest.raises(AmbiguousRoute, match="Ambiguous first-hop bearings"):
        gold_answer(
            venue=ambiguous_venue,
            closed_edges=[],
            junction="j_start",
            heading=0,
            dest="d_goal",
            turn_cw=None,
            listed=True,
        )

    # Directly check first_hop_bearings
    g = build_graph(ambiguous_venue)
    res = first_hop_bearings(g, "j_start", "d_goal")
    assert res is not None
    bearings, paths = res
    assert bearings == {0, 90}
    assert len(paths) == 2


def test_first_hop_same_src_and_dst(station_venue: Venue) -> None:
    """Verify first_hop_bearings returns None when src equals dst."""
    g = build_graph(station_venue)
    assert first_hop_bearings(g, "j_concourse", "j_concourse") is None


def test_first_hop_unknown_node(station_venue: Venue) -> None:
    """Verify first_hop_bearings returns None when an unknown node is supplied."""
    g = build_graph(station_venue)
    assert first_hop_bearings(g, "j_concourse", "nonexistent_destination") is None
    assert first_hop_bearings(g, "nonexistent_junction", "d_ticket") is None


def test_egocentric_turn_with_gold_answer(station_venue: Venue) -> None:
    """Verify viewer turns are correctly applied in gold_answer."""
    # Concourse to ticket is bearing 180. Heading 0 -> rel 180 (BACK).
    # Turn 90 clockwise -> rel 180 - 90 = 90 -> RIGHT.
    ans = gold_answer(
        venue=station_venue,
        closed_edges=[],
        junction="j_concourse",
        heading=0,
        dest="d_ticket",
        turn_cw=90,
        listed=True,
    )
    assert ans == "RIGHT"

    # Turn 180 -> rel 180 - 180 = 0 -> AHEAD.
    ans_180 = gold_answer(
        venue=station_venue,
        closed_edges=[],
        junction="j_concourse",
        heading=0,
        dest="d_ticket",
        turn_cw=180,
        listed=True,
    )
    assert ans_180 == "AHEAD"


def test_arrow_semantics_check() -> None:
    """Arrow semantics check: for all bearings b and headings h, verify arrow octant."""
    for b in VALID_BEARINGS:
        for h in VALID_BEARINGS:
            rel = relative_bearing(b, h)
            octant = to_octant(rel)
            expected_octant = to_octant((b - h) % 360)
            assert octant == expected_octant


def test_open_subgraph_filters_closed_edges(station_venue: Venue) -> None:
    """Verify open_subgraph excludes edges marked as closed."""
    v_closed = apply_closed_edges(station_venue, [("j_concourse", "d_ticket")])
    g = build_graph(v_closed)
    h = open_subgraph(g)
    assert not h.has_edge("j_concourse", "d_ticket")
    assert not h.has_edge("d_ticket", "j_concourse")
    assert g.has_edge("j_concourse", "d_ticket")
