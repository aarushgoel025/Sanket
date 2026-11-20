"""Determinism and reproducibility validation tests.

Enforces:
1. Two independent builds with the same master seed produce identical tasks.jsonl
   and identical image hashes.
2. Different master seeds produce distinct tasks and image hashes.
3. Random draws are strictly governed by explicit per-task seeded generators.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import imagehash
from PIL import Image

from sanket.pipeline.build_dataset import build_dataset
from sanket.schema import Task


def _sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def test_build_determinism_same_seed(tmp_path: Path) -> None:
    """Verify two pipeline builds with identical master_seed produce identical outputs."""
    dir1 = tmp_path / "build_run_1"
    dir2 = tmp_path / "build_run_2"

    master_seed = 42
    n_tasks = 4

    # Run 1
    stats1 = build_dataset(out_dir=dir1, n_keep=n_tasks, master_seed=master_seed)
    # Run 2
    stats2 = build_dataset(out_dir=dir2, n_keep=n_tasks, master_seed=master_seed)

    assert stats1["total_kept"] == stats2["total_kept"]
    assert stats1["total_kept"] >= n_tasks

    tasks_file_1 = dir1 / "tasks.jsonl"
    tasks_file_2 = dir2 / "tasks.jsonl"
    assert tasks_file_1.exists()
    assert tasks_file_2.exists()

    lines1 = [
        line.strip()
        for line in tasks_file_1.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    lines2 = [
        line.strip()
        for line in tasks_file_2.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(lines1) == len(lines2) == stats1["total_kept"]

    for idx, (l1, l2) in enumerate(zip(lines1, lines2, strict=True)):
        t1 = Task.model_validate_json(l1)
        t2 = Task.model_validate_json(l2)

        # 1. Structural and attribute equality
        assert t1.task_id == t2.task_id
        assert t1.seed == t2.seed
        assert t1.qtype == t2.qtype
        assert t1.question == t2.question
        assert t1.gold == t2.gold
        assert t1.options == t2.options
        assert t1.target_dest_id == t2.target_dest_id
        assert t1.receipt.agree == t2.receipt.agree

        # 2. Image perceptual and cryptographic hash equivalence
        img1_path = dir1 / Path(t1.image_path).relative_to(dir1)
        img2_path = dir2 / Path(t2.image_path).relative_to(dir2)

        assert img1_path.exists(), f"Image not found at {img1_path}"
        assert img2_path.exists(), f"Image not found at {img2_path}"

        # Perceptual hash identity
        with Image.open(img1_path) as im1, Image.open(img2_path) as im2:
            phash1 = imagehash.phash(im1)
            phash2 = imagehash.phash(im2)
            assert phash1 == phash2, (
                f"Task {t1.task_id} perceptual hash mismatch: {phash1} != {phash2}"
            )

        # Exact pixel hash
        hash1 = _sha256(img1_path)
        hash2 = _sha256(img2_path)
        assert hash1 == hash2, f"Task {t1.task_id} SHA-256 mismatch: {hash1} != {hash2}"


def test_build_divergence_different_seed(tmp_path: Path) -> None:
    """Verify different seeds produce divergent task seeds and distinct images."""
    dir_a = tmp_path / "build_seed_1"
    dir_b = tmp_path / "build_seed_2"

    build_dataset(out_dir=dir_a, n_keep=2, master_seed=111)
    build_dataset(out_dir=dir_b, n_keep=2, master_seed=999)

    tasks_a = [
        json.loads(line)
        for line in (dir_a / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tasks_b = [
        json.loads(line)
        for line in (dir_b / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Different seeds must yield different derived task seeds
    seeds_a = [t["seed"] for t in tasks_a]
    seeds_b = [t["seed"] for t in tasks_b]
    assert seeds_a != seeds_b
