"""Comprehensive test suite for dataset pipeline, verification gates, and CLI.

Tests:
1. Blind test language-prior filtering and fake adapter responses.
2. Structural signature deduplication and perceptual hashing.
3. Minimal counterfactual pair generation and differential verification.
4. Pipeline determinism under identical seeds.
5. Rejection logging and receipt validation.
6. Full dataset build acceptance criteria (agree, fidelity, visibility, pairs).
"""

import json
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from sanket.cli import app
from sanket.evaluate.adapters.fake import FakeBlindAdapter
from sanket.generator.scene_builder import build_scene, sample_knobs
from sanket.graph.venue import load_venue
from sanket.pipeline.build_dataset import build_dataset
from sanket.questions.templates import make_task
from sanket.schema import Task, Venue
from sanket.verify.blind_test import run_blind_test
from sanket.verify.dedupe import DedupeIndex
from sanket.verify.pairs import find_scene_field_differences

STATION_PATH = Path("config/venues/railway_station.yaml")
HOSPITAL_PATH = Path("config/venues/hospital.yaml")


@pytest.fixture
def station_venue() -> Venue:
    """Fixture providing Central Junction Station venue."""
    return load_venue(STATION_PATH)


@pytest.fixture
def hospital_venue() -> Venue:
    """Fixture providing City Hospital venue."""
    return load_venue(HOSPITAL_PATH)


# ==============================================================================
# 1. Blind Test Gate Tests
# ==============================================================================


def test_blind_test_rejection_and_acceptance(station_venue: Venue) -> None:
    """Assert blind test rejects tasks when guessing rate >= threshold and accepts otherwise."""
    rng = np.random.default_rng(123)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id="test_blind_01",
        seed=123,
        image_path="dummy.png",
        scene_path="dummy.json",
    )
    task.gold = "RIGHT"

    # Adapter that always guesses correctly (oracle) -> rate = 1.0 >= 0.67 -> reject
    oracle_adapter = FakeBlindAdapter(mode="oracle")
    ok, rate, guesses = run_blind_test(task, oracle_adapter, samples=3, threshold=0.67)
    assert ok is False
    assert rate == 1.0
    assert len(guesses) == 3

    # Adapter that never guesses correctly -> rate = 0.0 < 0.67 -> accept
    wrong_adapter = FakeBlindAdapter(mode="wrong")
    ok, rate, guesses = run_blind_test(task, wrong_adapter, samples=3, threshold=0.67)
    assert ok is True
    assert rate == 0.0
    assert len(guesses) == 3


# ==============================================================================
# 2. De-duplication Tests
# ==============================================================================


def test_dedupe_structural_signature_capping(station_venue: Venue) -> None:
    """Assert DedupeIndex caps identical structural signatures at max_per_signature."""
    rng = np.random.default_rng(456)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task = make_task(
        sb=sb,
        venue=station_venue,
        rng=rng,
        task_id="test_dedupe_sig",
        seed=456,
        image_path="dummy.png",
        scene_path="dummy.json",
    )

    # Index with max 2 per signature
    index = DedupeIndex(max_per_signature=2, phash_threshold=4)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 3 dummy distinct images
        img_paths: list[Path] = []
        for i in range(3):
            p = Path(tmpdir) / f"img_{i}.png"
            # Random noise image to avoid perceptual duplicate
            arr = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
            Image.fromarray(arr).save(p)
            img_paths.append(p)

        ok1, _ = index.check_and_add(task, sb.scene, img_paths[0])
        assert ok1 is True

        ok2, _ = index.check_and_add(task, sb.scene, img_paths[1])
        assert ok2 is True

        # 3rd task with same signature must be rejected
        ok3, reason = index.check_and_add(task, sb.scene, img_paths[2])
        assert ok3 is False
        assert "structural_cap_exceeded" in reason


def test_dedupe_perceptual_hash_near_duplicate(station_venue: Venue) -> None:
    """Assert DedupeIndex rejects perceptually identical images with distance <= 4."""
    rng = np.random.default_rng(789)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)

    task1 = make_task(sb, station_venue, rng, "task_phash_1", 789, "d.png", "d.json")
    task2 = make_task(sb, station_venue, rng, "task_phash_2", 790, "d.png", "d.json")
    task2.gold = "LEFT"  # Different signature so structural check passes

    index = DedupeIndex(max_per_signature=10, phash_threshold=4)

    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = Path(tmpdir) / "base.png"
        p2 = Path(tmpdir) / "near_dup.png"

        img = Image.new("RGB", (64, 64), color="red")
        img.save(p1)

        # Perturb single pixel (Hamming distance on 64-bit phash is 0 or 1)
        img_perturbed = img.copy()
        img_perturbed.putpixel((0, 0), (254, 0, 0))
        img_perturbed.save(p2)

        ok1, _ = index.check_and_add(task1, sb.scene, p1)
        assert ok1 is True

        ok2, reason = index.check_and_add(task2, sb.scene, p2)
        assert ok2 is False
        assert "perceptual_near_duplicate" in reason


# ==============================================================================
# 3. Minimal Counterfactual Pair Tests
# ==============================================================================


def test_find_scene_field_differences(station_venue: Venue) -> None:
    """Assert find_scene_field_differences precisely reports single and multi field changes."""
    rng = np.random.default_rng(101)
    knobs = sample_knobs(rng, "DIRECT")
    sb = build_scene(station_venue, "DIRECT", rng, knobs)
    scene_a = sb.scene

    # Identical scenes -> 0 diffs
    assert find_scene_field_differences(scene_a, scene_a) == []

    # Single entry arrow_angle difference
    scene_b = scene_a.model_copy(deep=True)
    scene_b.entries[0].arrow_angle = (scene_b.entries[0].arrow_angle + 45) % 360
    assert find_scene_field_differences(scene_a, scene_b) == ["entries[0].arrow_angle"]

    # Status difference
    scene_c = scene_a.model_copy(deep=True)
    scene_c.entries[0].status = "closed" if scene_c.entries[0].status == "open" else "open"
    assert find_scene_field_differences(scene_a, scene_c) == ["entries[0].status"]

    # Heading difference
    scene_d = scene_a.model_copy(deep=True)
    scene_d.heading = (scene_d.heading + 45) % 360
    assert find_scene_field_differences(scene_a, scene_d) == ["heading"]


# ==============================================================================
# 4. Pipeline Seed Determinism
# ==============================================================================


def test_pipeline_seed_determinism() -> None:
    """Assert building dataset twice with identical seed produces byte-identical tasks.jsonl."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        out1 = Path(tmp1)
        out2 = Path(tmp2)

        build_dataset(out_dir=out1, n_keep=6, master_seed=999)
        build_dataset(out_dir=out2, n_keep=6, master_seed=999)

        # Compare task records excluding volatile temporary directory paths
        tasks1 = [
            Task.model_validate_json(line).model_dump(exclude={"image_path", "scene_path"})
            for line in (out1 / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        tasks2 = [
            Task.model_validate_json(line).model_dump(exclude={"image_path", "scene_path"})
            for line in (out2 / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        assert tasks1 == tasks2
        assert len(tasks1) > 0


# ==============================================================================
# 5. Pipeline Rejection Logging and Receipts
# ==============================================================================


def test_pipeline_rejections_and_receipts() -> None:
    """Verify rejected.jsonl records valid reason codes and kept tasks have verified receipts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        stats = build_dataset(out_dir=out_dir, n_keep=12, master_seed=42)

        assert stats["total_kept"] >= 10
        assert (out_dir / "build_stats.json").exists()

        # Check rejected.jsonl
        rejected_file = out_dir / "rejected.jsonl"
        assert rejected_file.exists()
        rejections = [
            json.loads(line)
            for line in rejected_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        valid_reasons = {
            "ambiguous_route",
            "duplicate",
            "imbalanced",
            "blind_test_fail",
            "visibility_fail",
            "fidelity_fail",
            "solver_independent_mismatch",
            "venue_missing_junctions_or_destinations",
        }
        for rec in rejections:
            assert rec["reason"] in valid_reasons
            assert "task_id" in rec
            assert "seed" in rec
            assert "qtype" in rec

        # Check kept tasks
        tasks_file = out_dir / "tasks.jsonl"
        tasks = [
            Task.model_validate_json(line)
            for line in tasks_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        for t in tasks:
            assert t.receipt is not None
            assert t.receipt.agree is True
            assert t.receipt.fidelity_ok is True
            assert t.receipt.visibility_ok is True
            assert (out_dir / "images" / f"{t.task_id}.png").exists()
            assert (out_dir / "scenes" / f"{t.task_id}.json").exists()


# ==============================================================================
# 6. Full 60-Task Build Acceptance Criteria
# ==============================================================================


def test_full_60_tasks_acceptance_criteria() -> None:
    """Acceptance test: 60-task build completes with all checks passing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        stats = build_dataset(out_dir=out_dir, n_keep=60, master_seed=100)
        assert stats["total_kept"] >= 60

        tasks_file = out_dir / "tasks.jsonl"
        tasks = [
            Task.model_validate_json(line)
            for line in tasks_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        assert len(tasks) >= 60

        # 1. All kept tasks have agree, fidelity_ok, and visibility_ok true
        for t in tasks:
            assert t.receipt is not None
            assert t.receipt.agree is True, f"Task {t.task_id} failed solver-independent agreement"
            assert t.receipt.fidelity_ok is True, f"Task {t.task_id} failed fidelity check"
            assert t.receipt.visibility_ok is True, f"Task {t.task_id} failed visibility check"

        # 2. Rejection log exists
        assert (out_dir / "rejected.jsonl").exists()

        # 3. Minimal pair checks pass on at least some pairs
        pairs = [t for t in tasks if t.pair_id is not None]
        assert len(pairs) > 0, "Expected at least some counterfactual minimal pairs"
        pair_groups: dict[str, list[Task]] = defaultdict(list)
        for t in pairs:
            assert t.pair_id is not None
            pair_groups[t.pair_id].append(t)

        for group in pair_groups.values():
            if len(group) == 2:
                roles = {group[0].pair_role, group[1].pair_role}
                assert roles == {"a", "b"}
                assert group[0].gold != group[1].gold
                assert group[0].receipt is not None and group[0].receipt.pair_verified is True
                assert group[1].receipt is not None and group[1].receipt.pair_verified is True

        # 4. Class balance check: no single gold answer exceeds 25% within directional types
        by_qtype: dict[str, list[Task]] = defaultdict(list)
        for t in tasks:
            by_qtype[t.qtype].append(t)

        for qtype in ("DIRECT", "BINDING", "OVERRIDE", "EGOCENTRIC"):
            q_tasks = by_qtype.get(qtype, [])
            gold_counts: dict[str, int] = defaultdict(int)
            for t in q_tasks:
                gold_counts[t.gold] += 1
            total_type = len(q_tasks)
            max_allowed = max(2, int(np.ceil(total_type * 0.25)))
            for gold_ans, count in gold_counts.items():
                assert count <= max_allowed, (
                    f"Gold '{gold_ans}' occurred {count}/{total_type} in type '{qtype}'"
                )


def test_cli_build_command() -> None:
    """Assert typer CLI build command succeeds and generates artifacts."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        result = runner.invoke(app, ["build", "--n", "6", "--out", str(out_dir), "--seed", "123"])
        assert result.exit_code == 0
        assert (out_dir / "tasks.jsonl").exists()
        assert (out_dir / "rejected.jsonl").exists()
        assert (out_dir / "build_stats.json").exists()
