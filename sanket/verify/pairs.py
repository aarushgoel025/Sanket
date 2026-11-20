"""Counterfactual minimal-pair generator and validator.

Constructs minimal pairs by editing a copy of the venue (perturbing one edge bearing
at the junction or toggling an edge status), rebuilding the scene with identical
seed and knobs, and verifying that:
1. Exactly one scene field path differs.
2. Rendered images differ.
3. Gold reference answers differ.
4. Independent and solver answers agree on both tasks.
"""

import logging
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from sanket.generator.augment import augment
from sanket.generator.renderer import render_scene
from sanket.graph.solver import AmbiguousRoute, build_graph, first_hop_bearings, gold_answer
from sanket.schema import Scene, Task, Venue
from sanket.verify.fidelity import fidelity_ok
from sanket.verify.independent import independent_answer
from sanket.verify.receipt import build_receipt
from sanket.verify.visibility import visibility_ok

logger = logging.getLogger(__name__)

VALID_BEARINGS = [0, 45, 90, 135, 180, 225, 270, 315]


def find_scene_field_differences(scene_a: Scene, scene_b: Scene) -> list[str]:
    """Find all field paths that differ between two Scene specifications.

    Args:
        scene_a: Reference scene.
        scene_b: Perturbed scene.

    Returns:
        List of dot-notated field path strings where differences exist.
    """
    diffs: list[str] = []

    if scene_a.junction_id != scene_b.junction_id:
        diffs.append("junction_id")

    if scene_a.heading != scene_b.heading:
        diffs.append("heading")

    if sorted(scene_a.closed_edges) != sorted(scene_b.closed_edges):
        diffs.append("closed_edges")

    if len(scene_a.entries) != len(scene_b.entries):
        diffs.append("entries.length")
    else:
        for i, (ea, eb) in enumerate(zip(scene_a.entries, scene_b.entries)):
            if ea.dest_id != eb.dest_id:
                diffs.append(f"entries[{i}].dest_id")
            if ea.label != eb.label:
                diffs.append(f"entries[{i}].label")
            if ea.arrow_angle != eb.arrow_angle:
                diffs.append(f"entries[{i}].arrow_angle")
            if ea.status != eb.status:
                diffs.append(f"entries[{i}].status")
            if ea.source != eb.source:
                diffs.append(f"entries[{i}].source")

    if scene_a.distractors != scene_b.distractors:
        diffs.append("distractors")

    if scene_a.knobs != scene_b.knobs:
        diffs.append("knobs")

    return diffs


def build_minimal_pair(
    task_a: Task,
    scene_a: Scene,
    venue: Venue,
    image_a_path: Path | str,
    out_images_dir: Path,
    out_scenes_dir: Path,
    browser: Any = None,
    allowed_gold: set[str] | None = None,
) -> tuple[Task, Task, Scene, Path] | None:
    """Build and verify a counterfactual minimal pair for a given task.

    Attempts minimal arrow angle perturbation on target destination entry,
    adjusting venue topology accordingly, and verifies that:
    1. Exactly one scene field path differs.
    2. Rendered images differ.
    3. Gold reference answers differ and satisfy balance constraints if supplied.
    4. Independent and solver answers agree on both tasks.

    Args:
        task_a: Original validated benchmark task.
        scene_a: Original scene specification.
        venue: Venue graph model.
        image_a_path: Path to rendered task_a image.
        out_images_dir: Destination directory for pair member images.
        out_scenes_dir: Destination directory for pair member scene JSONs.
        browser: Optional running Playwright browser instance.
        allowed_gold: Optional set of permitted gold answers for task B to preserve balance.

    Returns:
        Tuple of (task_a_with_pair_info, task_b, scene_b, image_b_path), or None.
    """
    out_images_dir = Path(out_images_dir)
    out_scenes_dir = Path(out_scenes_dir)
    out_images_dir.mkdir(parents=True, exist_ok=True)
    out_scenes_dir.mkdir(parents=True, exist_ok=True)

    # 1. Identify target entries in scene_a
    target_entries = [
        i for i, e in enumerate(scene_a.entries) if e.dest_id == task_a.target_dest_id
    ]
    if not target_entries:
        return None

    # Prioritize active entry (notice if present, else permanent)
    notice_entries = [i for i in target_entries if scene_a.entries[i].source == "temporary_notice"]
    active_idx = notice_entries[0] if notice_entries else target_entries[0]

    # 2. Build candidate perturbations
    candidates: list[tuple[Scene, Venue]] = []
    curr_angle = scene_a.entries[active_idx].arrow_angle

    for delta in [45, 90, 135, 180, 225, 270, 315]:
        scene_b = scene_a.model_copy(deep=True)
        new_angle = (curr_angle + delta) % 360
        scene_b.entries[active_idx].arrow_angle = new_angle

        # Adjust venue copy so first hop bearing matches new_angle
        v_b = venue.model_copy(deep=True)
        g = build_graph(v_b)
        hop_res = first_hop_bearings(
            g, scene_b.junction_id, task_a.target_dest_id, open_only=(task_a.qtype != "CLOSURE")
        )
        if not hop_res:
            continue

        paths = hop_res[1]
        first_hop_node = paths[0][1]
        new_bearing = (new_angle + scene_b.heading) % 360

        for e in v_b.edges:
            if e.a == scene_b.junction_id and e.b == first_hop_node:
                e.bearing_ab = new_bearing  # type: ignore[assignment]
            elif e.b == scene_b.junction_id and e.a == first_hop_node:
                e.bearing_ab = (new_bearing + 180) % 360  # type: ignore[assignment]

        candidates.append((scene_b, v_b))

    # Evaluate perturbation candidates
    for scene_b, v_candidate in candidates:
        # Condition 1: Exactly one scene field path differs
        diff_paths = find_scene_field_differences(scene_a, scene_b)
        if len(diff_paths) != 1:
            continue

        # Condition 2: Solver and independent answer for candidate B
        try:
            solver_ans_b = gold_answer(
                venue=v_candidate,
                closed_edges=scene_b.closed_edges,
                junction=scene_b.junction_id,
                heading=scene_b.heading,
                dest=task_a.target_dest_id,
                turn_cw=task_a.turn_cw,
                listed=(task_a.qtype != "ABSENT"),
            )
        except (AmbiguousRoute, ValueError, nx.NetworkXError) as exc:
            logger.debug("Pair solver resolution failed: %s", exc)
            continue

        task_b_id = f"{task_a.task_id}_b"
        task_b = task_a.model_copy(deep=True)
        task_b.task_id = task_b_id
        task_b.gold = solver_ans_b

        indep_ans_b = independent_answer(scene_b, task_b)
        if indep_ans_b != solver_ans_b:
            continue

        # Condition 3: Gold answers must differ and be permitted
        if solver_ans_b == task_a.gold:
            continue
        if allowed_gold is not None and solver_ans_b not in allowed_gold:
            continue

        img_b_path = out_images_dir / f"{task_b_id}.png"
        raw_b_path = out_images_dir / f"{task_b_id}_raw.png"
        scene_b_path = out_scenes_dir / f"{task_b_id}.json"

        # Condition 4: Render and fidelity
        try:
            geo_b = render_scene(scene_b, v_candidate, raw_b_path, browser=browser)
            fid_ok, fid_reason = fidelity_ok(scene_b, geo_b)
            if not fid_ok:
                raw_b_path.unlink(missing_ok=True)
                continue
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Pair render failed: %s", exc)
            raw_b_path.unlink(missing_ok=True)
            continue

        # Condition 5: Augmentation and visibility
        try:
            trans_geo_b = augment(
                raw_b_path, geo_b, scene_b.knobs, np.random.default_rng(task_a.seed), img_b_path
            )
            raw_b_path.unlink(missing_ok=True)
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Pair augment failed: %s", exc)
            raw_b_path.unlink(missing_ok=True)
            img_b_path.unlink(missing_ok=True)
            continue

        task_b.image_path = str(img_b_path)
        task_b.scene_path = str(scene_b_path)

        vis_ok, vis_ratio = visibility_ok(scene_b, task_b, trans_geo_b)
        if not vis_ok:
            img_b_path.unlink(missing_ok=True)
            continue

        # Condition 6: Images must differ
        try:
            bytes_a = Path(image_a_path).read_bytes()
            bytes_b = Path(img_b_path).read_bytes()
            if bytes_a == bytes_b:
                img_b_path.unlink(missing_ok=True)
                continue
        except (OSError, ValueError) as exc:
            logger.debug("Pair image comparison failed: %s", exc)
            img_b_path.unlink(missing_ok=True)
            continue

        # Build receipt for task B
        task_b.receipt = build_receipt(
            task=task_b,
            scene=scene_b,
            solver_answer=solver_ans_b,
            independent_answer=indep_ans_b,
            fidelity=(fid_ok, fid_reason),
            visibility=(vis_ok, vis_ratio),
        )

        # Link pair
        pair_id = f"pair_{task_a.task_id}"
        task_a.pair_id = pair_id
        task_a.pair_role = "a"
        if task_a.receipt is not None:
            task_a.receipt.pair_verified = True

        task_b.pair_id = pair_id
        task_b.pair_role = "b"
        task_b.receipt.pair_verified = True

        return task_a, task_b, scene_b, img_b_path

    return None


__all__ = ["build_minimal_pair", "find_scene_field_differences"]
