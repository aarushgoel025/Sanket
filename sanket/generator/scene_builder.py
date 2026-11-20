"""Deterministic scene builder for generating wayfinding sign scenarios.

Combines venue topology, task random seed, question type, and difficulty knobs
to produce complete, auditable Scene specifications.
"""

from dataclasses import dataclass

import numpy as np

from sanket.config import DefaultConfig
from sanket.generator.distractors import generate_distractors
from sanket.graph.orientation import relative_bearing
from sanket.graph.solver import (
    apply_closed_edges,
    build_graph,
    first_hop_bearings,
)
from sanket.schema import (
    VALID_BEARINGS,
    Bearing,
    BoardEntry,
    Knobs,
    Label,
    Node,
    Scene,
    Venue,
)


class RejectScene(Exception):
    """Raised when a valid scene cannot be constructed for a venue and question type."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class SceneBuild:
    """Container holding the constructed scene, target destination ID, and question type."""

    scene: Scene
    target_dest_id: str
    qtype: str = ""


def sample_knobs(
    rng: np.random.Generator,
    qtype: str,
    cfg: DefaultConfig | None = None,
) -> Knobs:
    """Deterministically sample difficulty and environmental knobs.

    Args:
        rng: Seeded numpy random generator.
        qtype: Benchmark question type.
        cfg: Optional default configuration.

    Returns:
        Sampled Knobs model.
    """
    if qtype == "BINDING":
        n_entries = int(rng.integers(4, 9))
        template = str(rng.choice(["board_grid", "board_gantry"]))
    elif qtype == "EGOCENTRIC":
        n_entries = int(rng.integers(2, 9))
        template = str(rng.choice(["board_gantry", "board_list"]))
    else:
        n_entries = int(rng.integers(2, 9))
        template = "board_list"

    script_choices = [["en"], ["en", "hi"], ["en", "hi", "regional"]]
    script_idx = int(rng.integers(0, len(script_choices)))
    scripts = list(script_choices[script_idx])

    perspective_deg = round(float(rng.uniform(0.0, 25.0)), 2)
    blur = round(float(rng.uniform(0.0, 2.5)), 2)
    noise = round(float(rng.uniform(0.0, 0.06)), 4)
    lighting = round(float(rng.uniform(0.0, 0.4)), 2)
    clutter = int(rng.integers(0, 7))
    occlusion = round(float(rng.uniform(0.0, 0.15)), 3)
    jpeg_quality = int(rng.integers(60, 96))

    return Knobs(
        n_entries=n_entries,
        scripts=scripts,
        perspective_deg=perspective_deg,
        blur=blur,
        noise=noise,
        lighting=lighting,
        clutter=clutter,
        occlusion=occlusion,
        jpeg_quality=jpeg_quality,
        template=template,
    )


def _filter_label(label: Label, scripts: list[str]) -> Label:
    """Filter label to only expose scripts selected by knobs."""
    return Label(
        en=label.en,
        hi=label.hi if "hi" in scripts else None,
        regional=label.regional if "regional" in scripts else None,
        regional_script=label.regional_script if "regional" in scripts else None,
    )


def _find_similar_cluster(
    candidates: list[tuple[Node, int]],
) -> list[tuple[Node, int]]:
    """Group candidates by label prefix or category to support BINDING tasks."""
    by_word: dict[str, list[tuple[Node, int]]] = {}
    by_category: dict[str, list[tuple[Node, int]]] = {}

    for node, bearing in candidates:
        first_word = node.label.en.split()[0].strip() if node.label.en else ""
        if first_word:
            by_word.setdefault(first_word, []).append((node, bearing))
        if node.category:
            by_category.setdefault(node.category, []).append((node, bearing))

    for group in by_word.values():
        if len(group) >= 2:
            return group

    for group in by_category.values():
        if len(group) >= 2:
            return group

    return candidates


def build_scene(
    venue: Venue,
    qtype: str,
    rng: np.random.Generator,
    knobs: Knobs,
) -> SceneBuild:
    """Deterministically construct a scene for a venue and question type.

    Args:
        venue: Physical venue topology graph.
        qtype: Benchmark question type (DIRECT, BINDING, CLOSURE, OVERRIDE, EGOCENTRIC, ABSENT).
        rng: Seeded numpy random generator.
        knobs: Difficulty and environmental knobs.

    Returns:
        SceneBuild containing the populated Scene and target destination ID.

    Raises:
        RejectScene: If scene cannot be generated due to ambiguity or topology constraints.
    """
    junction_nodes = sorted([n for n in venue.nodes if n.kind == "junction"], key=lambda n: n.id)
    destination_nodes = sorted(
        [n for n in venue.nodes if n.kind == "destination"], key=lambda n: n.id
    )

    if not junction_nodes or not destination_nodes:
        raise RejectScene("venue_missing_junctions_or_destinations")

    # Enforce BINDING constraints on knobs if necessary
    active_knobs = knobs.model_copy()
    if qtype == "BINDING":
        updates: dict = {}
        if active_knobs.template not in ("board_grid", "board_gantry"):
            updates["template"] = str(rng.choice(["board_grid", "board_gantry"]))
        if active_knobs.n_entries < 4:
            updates["n_entries"] = 4
        if updates:
            active_knobs = active_knobs.model_copy(update=updates)

    g_full = build_graph(venue)
    saw_ambiguity = False

    # Attempt up to 20 candidate configurations
    for _ in range(20):
        junction = junction_nodes[int(rng.integers(0, len(junction_nodes)))]
        heading = int(rng.choice(VALID_BEARINGS))

        # Check reachable destinations and first-hop uniqueness on full graph
        reachable_full: list[tuple[Node, int]] = []
        has_ambiguity_here = False

        for d in destination_nodes:
            res = first_hop_bearings(g_full, junction.id, d.id, open_only=True)
            if res is None:
                continue
            bearings, _ = res
            if len(bearings) > 1:
                has_ambiguity_here = True
                saw_ambiguity = True
                continue
            bearing = next(iter(bearings))
            reachable_full.append((d, bearing))

        if has_ambiguity_here and not reachable_full:
            continue

        if qtype in ("DIRECT", "EGOCENTRIC"):
            if len(reachable_full) < active_knobs.n_entries:
                continue

            target_idx = int(rng.integers(0, len(reachable_full)))
            target_node, target_bearing = reachable_full[target_idx]

            remaining = [item for item in reachable_full if item[0].id != target_node.id]
            n_other = active_knobs.n_entries - 1
            chosen_other_indices = rng.choice(len(remaining), size=n_other, replace=False)
            chosen_items = [(target_node, target_bearing)] + [
                remaining[idx] for idx in chosen_other_indices
            ]

            # Deterministic permutation of entries order
            perm_order = rng.permutation(len(chosen_items))
            entries: list[BoardEntry] = []
            for idx in perm_order:
                node, bearing = chosen_items[idx]
                arrow_angle = relative_bearing(bearing, heading)
                entries.append(
                    BoardEntry(
                        dest_id=node.id,
                        label=_filter_label(node.label, active_knobs.scripts),
                        arrow_angle=cast_bearing(arrow_angle),
                        status="open",
                        source="permanent",
                    )
                )

            scene_id = (
                f"scene_{venue.id}_{junction.id}_{qtype.lower()}_{int(rng.integers(10000, 99999))}"
            )
            distractors = generate_distractors(active_knobs.clutter, active_knobs.template, rng)

            scene = Scene(
                scene_id=scene_id,
                venue_id=venue.id,
                junction_id=junction.id,
                heading=cast_bearing(heading),
                entries=entries,
                distractors=distractors,
                knobs=active_knobs,
                closed_edges=[],
            )
            return SceneBuild(scene=scene, target_dest_id=target_node.id, qtype=qtype)

        elif qtype == "BINDING":
            if len(reachable_full) < active_knobs.n_entries:
                continue

            cluster = _find_similar_cluster(reachable_full)
            target_idx = int(rng.integers(0, len(cluster)))
            target_node, target_bearing = cluster[target_idx]

            # Prioritize other members of the cluster
            other_cluster = [item for item in cluster if item[0].id != target_node.id]
            non_cluster = [
                item for item in reachable_full if item[0].id not in {c[0].id for c in cluster}
            ]

            needed_others = active_knobs.n_entries - 1
            chosen_others: list[tuple[Node, int]] = []

            if len(other_cluster) >= needed_others:
                sel_indices = rng.choice(len(other_cluster), size=needed_others, replace=False)
                chosen_others.extend(other_cluster[idx] for idx in sel_indices)
            else:
                chosen_others.extend(other_cluster)
                remaining_needed = needed_others - len(chosen_others)
                if len(non_cluster) < remaining_needed:
                    continue
                sel_indices = rng.choice(len(non_cluster), size=remaining_needed, replace=False)
                chosen_others.extend(non_cluster[idx] for idx in sel_indices)

            chosen_items = [(target_node, target_bearing)] + chosen_others
            perm_order = rng.permutation(len(chosen_items))

            entries = []
            for idx in perm_order:
                node, bearing = chosen_items[idx]
                arrow_angle = relative_bearing(bearing, heading)
                entries.append(
                    BoardEntry(
                        dest_id=node.id,
                        label=_filter_label(node.label, active_knobs.scripts),
                        arrow_angle=cast_bearing(arrow_angle),
                        status="open",
                        source="permanent",
                    )
                )

            scene_id = (
                f"scene_{venue.id}_{junction.id}_{qtype.lower()}_{int(rng.integers(10000, 99999))}"
            )
            distractors = generate_distractors(active_knobs.clutter, active_knobs.template, rng)

            scene = Scene(
                scene_id=scene_id,
                venue_id=venue.id,
                junction_id=junction.id,
                heading=cast_bearing(heading),
                entries=entries,
                distractors=distractors,
                knobs=active_knobs,
                closed_edges=[],
            )
            return SceneBuild(scene=scene, target_dest_id=target_node.id, qtype=qtype)

        elif qtype == "CLOSURE":
            if len(reachable_full) < active_knobs.n_entries:
                continue

            # Pick target from reachable
            target_idx = int(rng.integers(0, len(reachable_full)))
            target_node, target_full_bearing = reachable_full[target_idx]

            # Close all edges incident to the target destination
            incident_edges = [
                (e.a, e.b) for e in venue.edges if e.a == target_node.id or e.b == target_node.id
            ]
            if not incident_edges:
                continue

            v_closed = apply_closed_edges(venue, incident_edges)
            g_closed = build_graph(v_closed)

            # Verify no open path exists to target, but full path does exist
            if (
                first_hop_bearings(g_closed, junction.id, target_node.id, open_only=True)
                is not None
            ):
                continue
            if first_hop_bearings(g_closed, junction.id, target_node.id, open_only=False) is None:
                continue

            # Check that enough other destinations remain open and unambiguous
            remaining_reachable: list[tuple[Node, int]] = []
            for d in destination_nodes:
                if d.id == target_node.id:
                    continue
                res = first_hop_bearings(g_closed, junction.id, d.id, open_only=True)
                if res is None:
                    continue
                bearings, _ = res
                if len(bearings) == 1:
                    remaining_reachable.append((d, next(iter(bearings))))

            n_other = active_knobs.n_entries - 1
            if len(remaining_reachable) < n_other:
                continue

            chosen_other_indices = rng.choice(len(remaining_reachable), size=n_other, replace=False)
            chosen_others = [remaining_reachable[idx] for idx in chosen_other_indices]

            # Build target entry with full-graph arrow and status "closed"
            target_arrow = relative_bearing(target_full_bearing, heading)
            target_entry = BoardEntry(
                dest_id=target_node.id,
                label=_filter_label(target_node.label, active_knobs.scripts),
                arrow_angle=cast_bearing(target_arrow),
                status="closed",
                source="permanent",
            )

            other_entries = [
                BoardEntry(
                    dest_id=node.id,
                    label=_filter_label(node.label, active_knobs.scripts),
                    arrow_angle=cast_bearing(relative_bearing(bearing, heading)),
                    status="open",
                    source="permanent",
                )
                for node, bearing in chosen_others
            ]

            all_entries = [target_entry] + other_entries
            perm_order = rng.permutation(len(all_entries))
            final_entries = [all_entries[idx] for idx in perm_order]

            scene_id = (
                f"scene_{venue.id}_{junction.id}_{qtype.lower()}_{int(rng.integers(10000, 99999))}"
            )
            distractors = generate_distractors(active_knobs.clutter, active_knobs.template, rng)

            scene = Scene(
                scene_id=scene_id,
                venue_id=venue.id,
                junction_id=junction.id,
                heading=cast_bearing(heading),
                entries=final_entries,
                distractors=distractors,
                knobs=active_knobs,
                closed_edges=incident_edges,
            )
            return SceneBuild(scene=scene, target_dest_id=target_node.id, qtype=qtype)

        elif qtype == "OVERRIDE":
            # Search for (target, edge_to_close) where alternate route has different first hop
            candidates_override = []

            for d, stale_bearing in reachable_full:
                stale_arrow = relative_bearing(stale_bearing, heading)
                # Find shortest path edges in full graph
                full_paths_res = first_hop_bearings(g_full, junction.id, d.id, open_only=True)
                if full_paths_res is None:
                    continue
                _, paths = full_paths_res

                for p in paths:
                    for k in range(len(p) - 1):
                        u, v = p[k], p[k + 1]
                        test_edge = (u, v)
                        v_test = apply_closed_edges(venue, [test_edge])
                        g_test = build_graph(v_test)

                        open_res = first_hop_bearings(g_test, junction.id, d.id, open_only=True)
                        if open_res is None:
                            continue
                        new_bearings, _ = open_res
                        if len(new_bearings) != 1:
                            saw_ambiguity = True
                            continue
                        new_bearing = next(iter(new_bearings))
                        notice_arrow = relative_bearing(new_bearing, heading)

                        if notice_arrow == stale_arrow:
                            continue

                        # Check reachable others in g_test
                        other_open: list[tuple[Node, int]] = []
                        for od in destination_nodes:
                            if od.id == d.id:
                                continue
                            o_res = first_hop_bearings(g_test, junction.id, od.id, open_only=True)
                            if o_res is not None and len(o_res[0]) == 1:
                                other_open.append((od, next(iter(o_res[0]))))

                        if len(other_open) >= active_knobs.n_entries - 1:
                            candidates_override.append(
                                (d, test_edge, stale_arrow, notice_arrow, other_open)
                            )

            if not candidates_override:
                continue

            chosen_override_idx = int(rng.integers(0, len(candidates_override)))
            (
                target_node,
                closed_edge,
                stale_arrow,
                notice_arrow,
                other_open,
            ) = candidates_override[chosen_override_idx]

            n_other = active_knobs.n_entries - 1
            chosen_other_indices = rng.choice(len(other_open), size=n_other, replace=False)
            chosen_others = [other_open[idx] for idx in chosen_other_indices]

            # Permanent entry shows stale full-graph arrow
            target_perm_entry = BoardEntry(
                dest_id=target_node.id,
                label=_filter_label(target_node.label, active_knobs.scripts),
                arrow_angle=cast_bearing(stale_arrow),
                status="open",
                source="permanent",
            )

            other_entries = [
                BoardEntry(
                    dest_id=node.id,
                    label=_filter_label(node.label, active_knobs.scripts),
                    arrow_angle=cast_bearing(relative_bearing(bearing, heading)),
                    status="open",
                    source="permanent",
                )
                for node, bearing in chosen_others
            ]

            perm_entries = [target_perm_entry] + other_entries
            perm_order = rng.permutation(len(perm_entries))
            final_perm_entries = [perm_entries[idx] for idx in perm_order]

            # Temporary notice entry shows the new open-route arrow
            notice_entry = BoardEntry(
                dest_id=target_node.id,
                label=_filter_label(target_node.label, active_knobs.scripts),
                arrow_angle=cast_bearing(notice_arrow),
                status="open",
                source="temporary_notice",
            )

            all_entries = final_perm_entries + [notice_entry]

            scene_id = (
                f"scene_{venue.id}_{junction.id}_{qtype.lower()}_{int(rng.integers(10000, 99999))}"
            )
            distractors = generate_distractors(active_knobs.clutter, active_knobs.template, rng)

            scene = Scene(
                scene_id=scene_id,
                venue_id=venue.id,
                junction_id=junction.id,
                heading=cast_bearing(heading),
                entries=all_entries,
                distractors=distractors,
                knobs=active_knobs,
                closed_edges=[closed_edge],
            )
            return SceneBuild(scene=scene, target_dest_id=target_node.id, qtype=qtype)

        elif qtype == "ABSENT":
            if len(reachable_full) < active_knobs.n_entries + 1:
                continue

            target_idx = int(rng.integers(0, len(reachable_full)))
            target_node, _ = reachable_full[target_idx]

            remaining = [item for item in reachable_full if item[0].id != target_node.id]
            chosen_indices = rng.choice(len(remaining), size=active_knobs.n_entries, replace=False)
            chosen_items = [remaining[idx] for idx in chosen_indices]

            perm_order = rng.permutation(len(chosen_items))
            entries = []
            for idx in perm_order:
                node, bearing = chosen_items[idx]
                arrow_angle = relative_bearing(bearing, heading)
                entries.append(
                    BoardEntry(
                        dest_id=node.id,
                        label=_filter_label(node.label, active_knobs.scripts),
                        arrow_angle=cast_bearing(arrow_angle),
                        status="open",
                        source="permanent",
                    )
                )

            scene_id = (
                f"scene_{venue.id}_{junction.id}_{qtype.lower()}_{int(rng.integers(10000, 99999))}"
            )
            distractors = generate_distractors(active_knobs.clutter, active_knobs.template, rng)

            scene = Scene(
                scene_id=scene_id,
                venue_id=venue.id,
                junction_id=junction.id,
                heading=cast_bearing(heading),
                entries=entries,
                distractors=distractors,
                knobs=active_knobs,
                closed_edges=[],
            )
            return SceneBuild(scene=scene, target_dest_id=target_node.id, qtype=qtype)

        else:
            raise ValueError(f"Unknown question type: {qtype}")

    if saw_ambiguity:
        raise RejectScene("ambiguous_route")
    raise RejectScene(f"unable_to_build_{qtype.lower()}_scene")


def cast_bearing(angle: int) -> Bearing:
    """Validate and cast angle to Bearing Literal."""
    assert angle in VALID_BEARINGS, f"Angle {angle} is not a multiple of 45 in [0, 315]"
    return angle  # type: ignore[return-value]
