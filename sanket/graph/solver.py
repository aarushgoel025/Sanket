"""Shortest-path solver and ground-truth answer resolution [HUMAN-OWNED].

Derives reference wayfinding decisions from venue graphs and scene states.
"""

from typing import cast

import networkx as nx

from sanket.graph.orientation import apply_turn, relative_bearing, to_octant
from sanket.schema import Answer, Venue


class AmbiguousRoute(Exception):
    """Raised when shortest paths yield multiple distinct first-hop bearings."""


def build_graph(venue: Venue) -> nx.DiGraph:
    """Build a directed graph from venue topology.

    Adds edges in both directions, computing reverse bearing as (bearing + 180) % 360.
    """
    G = nx.DiGraph()
    for e in venue.edges:
        G.add_edge(e.a, e.b, bearing=e.bearing_ab, length=e.length, status=e.status)
        G.add_edge(
            e.b,
            e.a,
            bearing=(e.bearing_ab + 180) % 360,
            length=e.length,
            status=e.status,
        )
    return G


def open_subgraph(G: nx.DiGraph) -> nx.DiGraph:
    """Return an edge subgraph containing only edges with status == 'open'."""
    return G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if d["status"] == "open"])


def first_hop_bearings(
    G: nx.DiGraph, src: str, dst: str, open_only: bool = True
) -> tuple[set[int], list[list[str]]] | None:
    """Find all shortest paths from src to dst and return distinct first-hop bearings and paths.

    Returns None if src == dst or if no path exists.
    """
    if src == dst:
        return None
    H = open_subgraph(G) if open_only else G
    try:
        paths = list(nx.all_shortest_paths(H, src, dst, weight="length"))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return {G[p[0]][p[1]]["bearing"] for p in paths}, paths


def apply_closed_edges(venue: Venue, closed_edges: list[tuple[str, str]]) -> Venue:
    """Return a copy of venue with the specified edges set to status='closed'."""
    closed_set = set(closed_edges) | {(v, u) for u, v in closed_edges}
    new_edges = [
        e.model_copy(update={"status": "closed"})
        if (e.a, e.b) in closed_set or (e.b, e.a) in closed_set
        else e.model_copy()
        for e in venue.edges
    ]
    return venue.model_copy(update={"edges": new_edges})


def gold_answer(
    venue: Venue,
    closed_edges: list[tuple[str, str]],
    junction: str,
    heading: int,
    dest: str,
    turn_cw: int | None = None,
    listed: bool = True,
) -> Answer:
    """Resolve ground-truth answer for a wayfinding query from venue graph and scene state.

    Rules:
    - If not listed -> 'NOT_INDICATED'
    - If no open path but path exists in full graph -> 'CLOSED'
    - If set of first-hop bearings has >1 element -> raises AmbiguousRoute
    - Otherwise compute relative bearing, apply turn if specified, and return octant.
    """
    if not listed:
        return "NOT_INDICATED"

    v_closed = apply_closed_edges(venue, closed_edges)
    G = build_graph(v_closed)

    open_res = first_hop_bearings(G, junction, dest, open_only=True)
    if open_res is None:
        full_res = first_hop_bearings(G, junction, dest, open_only=False)
        if full_res is not None:
            return "CLOSED"
        return "NOT_INDICATED"

    bearings, _paths = open_res
    if len(bearings) > 1:
        raise AmbiguousRoute(
            f"Ambiguous first-hop bearings {bearings} from '{junction}' to '{dest}'"
        )

    bearing = next(iter(bearings))
    rel = relative_bearing(bearing, heading)
    if turn_cw is not None:
        rel = apply_turn(rel, turn_cw)
    return cast(Answer, to_octant(rel))
