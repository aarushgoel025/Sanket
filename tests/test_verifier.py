"""Unit tests for independent verification, render fidelity, visibility, and receipts.

Tests error injection (wrong arrow, missing closed mark, occluded/out-of-bounds evidence)
and proves 20 clean tasks of each benchmark type pass all three verification layers.
"""

import ast
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sanket.generator.augment import augment
from sanket.generator.renderer import render_scene
from sanket.generator.scene_builder import build_scene, sample_knobs
from sanket.graph.solver import gold_answer
from sanket.graph.venue import load_venue
from sanket.questions.templates import make_task
from sanket.schema import BoardEntry, ElementGeo, Geometry, Venue
from sanket.verify.fidelity import fidelity_ok
from sanket.verify.independent import independent_answer
from sanket.verify.receipt import build_receipt, is_task_kept
from sanket.verify.visibility import visibility_ok

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


@pytest.fixture(scope="module")
def shared_browser():
    """Module-scoped browser to accelerate bulk render verification."""
    from playwright.sync_api import sync_playwright

    from sanket.generator.renderer import _get_browser_executable

    with sync_playwright() as p:
        exec_path = _get_browser_executable()
        launch_args = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--allow-file-access-from-files",
                "--disable-web-security",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
            ],
        }
        if exec_path:
            launch_args["executable_path"] = exec_path
        browser = p.chromium.launch(**launch_args)
        yield browser
        browser.close()


def test_independent_imports_nothing_from_solver() -> None:
    """Verify that independent.py imports nothing from solver.py or graph layout modules."""
    indep_file = Path("sanket/verify/independent.py")
    tree = ast.parse(indep_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "solver" not in alias.name, f"Forbidden import: {alias.name}"
                assert "venue" not in alias.name, f"Forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "solver" not in mod, f"Forbidden from-import module: {mod}"
            assert "venue" not in mod, f"Forbidden from-import module: {mod}"


def test_injected_wrong_arrow_angle_detected(station_venue: Venue) -> None:
    """Injected wrong arrow angle in scene causes independent answer to disagree with solver."""
    rng = np.random.default_rng(101)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id="task_wrong_arrow",
        seed=101,
        image_path="test.png",
        scene_path="test.json",
    )

    # Clean agreement baseline
    clean_solver = gold_answer(
        venue=station_venue,
        closed_edges=sb.scene.closed_edges,
        junction=sb.scene.junction_id,
        heading=sb.scene.heading,
        dest=sb.target_dest_id,
        turn_cw=task.turn_cw,
        listed=True,
    )
    clean_indep = independent_answer(sb.scene, task)
    assert clean_indep == clean_solver == task.gold

    # Inject bug: rotate target arrow by 180 degrees
    mutated_entries: list[BoardEntry] = []
    for e in sb.scene.entries:
        if e.dest_id == sb.target_dest_id:
            wrong_angle = (e.arrow_angle + 180) % 360
            mutated_entries.append(e.model_copy(update={"arrow_angle": wrong_angle}))
        else:
            mutated_entries.append(e.model_copy())

    corrupt_scene = sb.scene.model_copy(update={"entries": mutated_entries})
    corrupt_indep = independent_answer(corrupt_scene, task)

    # Disagreement detected
    assert corrupt_indep != clean_solver
    receipt = build_receipt(
        task=task,
        scene=corrupt_scene,
        solver_answer=clean_solver,
        independent_answer=corrupt_indep,
        fidelity=True,
        visibility=(True, 1.0),
    )
    assert receipt.agree is False
    assert is_task_kept(receipt) is False


def test_injected_missing_closed_mark_fails_fidelity(station_venue: Venue) -> None:
    """Injected missing closed mark for a closed destination triggers fidelity rejection."""
    rng = np.random.default_rng(202)
    knobs = sample_knobs(rng, "CLOSURE")
    sb = build_scene(station_venue, "CLOSURE", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "closure.png"
        geo = render_scene(sb.scene, station_venue, out_png)

        # Baseline fidelity must pass
        valid, msg = fidelity_ok(sb.scene, geo)
        assert valid is True
        assert msg == ""

        # Inject bug: strip all closed_mark elements from geometry
        corrupt_elements = [e for e in geo.elements if e.role != "closed_mark"]
        corrupt_geo = Geometry(elements=corrupt_elements)

        failed, reason = fidelity_ok(sb.scene, corrupt_geo)
        assert failed is False
        assert "closed mark missing" in reason.lower()


def test_injected_arrow_mismatch_fails_fidelity(station_venue: Venue) -> None:
    """Injected arrow rotation mismatch in geometry triggers fidelity rejection."""
    rng = np.random.default_rng(303)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "direct.png"
        geo = render_scene(sb.scene, station_venue, out_png)

        # Corrupt arrow angle in geometry
        corrupt_elements: list[ElementGeo] = []
        for e in geo.elements:
            if e.role == "arrow" and e.dest_id == sb.target_dest_id:
                corrupt_elements.append(
                    ElementGeo(
                        role=e.role,
                        dest_id=e.dest_id,
                        angle=((e.angle or 0) + 90) % 360,
                        text=e.text,
                        bbox=e.bbox,
                        occluded_ratio=e.occluded_ratio,
                        source=e.source,
                    )
                )
            else:
                corrupt_elements.append(e)

        corrupt_geo = Geometry(elements=corrupt_elements)
        failed, reason = fidelity_ok(sb.scene, corrupt_geo)
        assert failed is False
        assert "arrow angle" in reason.lower()


def test_injected_visibility_out_of_bounds_fails(station_venue: Venue) -> None:
    """Evidence element outside image viewport triggers visibility rejection."""
    rng = np.random.default_rng(404)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id="task_vis_bounds",
        seed=404,
        image_path="test.png",
        scene_path="test.json",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "vis_base.png"
        geo = render_scene(sb.scene, station_venue, out_png)

        # Corrupt target label bbox to be outside viewport (x < 0)
        corrupt_elements: list[ElementGeo] = []
        for e in geo.elements:
            if e.role == "label" and e.dest_id == sb.target_dest_id:
                corrupt_elements.append(
                    ElementGeo(
                        role=e.role,
                        dest_id=e.dest_id,
                        angle=e.angle,
                        text=e.text,
                        bbox=(-15.0, e.bbox[1], e.bbox[2], e.bbox[3]),
                        occluded_ratio=e.occluded_ratio,
                        source=e.source,
                    )
                )
            else:
                corrupt_elements.append(e)

        corrupt_geo = Geometry(elements=corrupt_elements)
        is_vis, _ = visibility_ok(sb.scene, task, corrupt_geo, image_size=(1280, 720))
        assert is_vis is False


def test_injected_visibility_excessive_occlusion_fails(station_venue: Venue) -> None:
    """Evidence element with occluded_ratio > 0.10 triggers visibility rejection."""
    rng = np.random.default_rng(505)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id="task_vis_occ",
        seed=505,
        image_path="test.png",
        scene_path="test.json",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "vis_occ.png"
        geo = render_scene(sb.scene, station_venue, out_png)

        # Corrupt target arrow to have occluded_ratio = 0.30
        corrupt_elements: list[ElementGeo] = []
        for e in geo.elements:
            if e.role == "arrow" and e.dest_id == sb.target_dest_id:
                corrupt_elements.append(
                    ElementGeo(
                        role=e.role,
                        dest_id=e.dest_id,
                        angle=e.angle,
                        text=e.text,
                        bbox=e.bbox,
                        occluded_ratio=0.30,
                        source=e.source,
                    )
                )
            else:
                corrupt_elements.append(e)

        corrupt_geo = Geometry(elements=corrupt_elements)
        is_vis, ratio = visibility_ok(sb.scene, task, corrupt_geo, image_size=(1280, 720))
        assert is_vis is False
        assert ratio < 1.0


@pytest.mark.parametrize("qtype", QUESTION_TYPES)
def test_twenty_correct_tasks_of_each_type_pass_all_checks(
    station_venue: Venue, qtype: str, shared_browser: Any
) -> None:
    """Verify 20 tasks of each question type pass independent, fidelity, and visibility checks."""
    for idx in range(20):
        seed = 1000 + (idx * 17)
        rng = np.random.default_rng(seed)

        knobs = sample_knobs(rng, qtype)
        sb = build_scene(station_venue, qtype, rng, knobs)

        task = make_task(
            sb=sb,
            venue=station_venue,
            rng=rng,
            task_id=f"gate_{qtype}_{idx:02d}",
            seed=seed,
            image_path=f"images/{qtype}_{idx}.png",
            scene_path=f"scenes/{qtype}_{idx}.json",
        )

        # 1. Independent solver agreement check
        solver_ans = gold_answer(
            venue=station_venue,
            closed_edges=sb.scene.closed_edges,
            junction=sb.scene.junction_id,
            heading=sb.scene.heading,
            dest=sb.target_dest_id,
            turn_cw=task.turn_cw,
            listed=(qtype != "ABSENT"),
        )
        indep_ans = independent_answer(sb.scene, task)
        assert indep_ans == solver_ans == task.gold

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_png = Path(tmpdir) / "raw.png"
            geo = render_scene(sb.scene, station_venue, raw_png, browser=shared_browser)

            # 2. Render fidelity check
            fid_ok, fid_reason = fidelity_ok(sb.scene, geo)
            assert fid_ok is True, f"Fidelity failed for {qtype} idx {idx}: {fid_reason}"

            # 3. Augmentation and visibility check
            aug_png = Path(tmpdir) / "aug.png"
            trans_geo = augment(raw_png, geo, sb.scene.knobs, rng, aug_png)

            vis_ok, vis_ratio = visibility_ok(sb.scene, task, trans_geo)
            assert vis_ok is True, f"Visibility failed for {qtype} idx {idx} (ratio: {vis_ratio})"

            # 4. Receipt assembly and acceptance gate
            receipt = build_receipt(
                task=task,
                scene=sb.scene,
                solver_answer=solver_ans,
                independent_answer=indep_ans,
                fidelity=(fid_ok, fid_reason),
                visibility=(vis_ok, vis_ratio),
            )
            assert receipt.agree is True
            assert is_task_kept(receipt) is True
