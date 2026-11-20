"""Deduplication filter using structural signatures and perceptual hashing.

Removes redundant tasks based on structural sign signatures and perceptual
image hashing (phash) to guarantee diverse benchmark task distributions.
"""

from collections import defaultdict
from pathlib import Path

import imagehash
from PIL import Image

from sanket.schema import Scene, Task


def structural_signature(
    task: Task, scene: Scene
) -> tuple[str, int, int, str, str, tuple[str, ...]]:
    """Compute the structural signature tuple for a task and scene.

    Signature components:
    (qtype, n_entries, target_index_on_board, gold, template, scripts)

    Args:
        task: Benchmark task model.
        scene: Scene specification model.

    Returns:
        Canonical tuple signature.
    """
    target_idx = -1
    for idx, entry in enumerate(scene.entries):
        if entry.dest_id == task.target_dest_id:
            target_idx = idx
            break

    return (
        str(task.qtype),
        len(scene.entries),
        target_idx,
        str(task.gold),
        str(scene.knobs.template),
        tuple(sorted(scene.knobs.scripts)),
    )


def compute_phash(image_path: Path | str) -> imagehash.ImageHash:
    """Compute perceptual image hash (phash) for an image file.

    Args:
        image_path: Path to PNG image.

    Returns:
        ImageHash object.
    """
    with Image.open(image_path) as img:
        return imagehash.phash(img)


class DedupeIndex:
    """Stateful deduplication index tracking structural signatures and perceptual hashes."""

    def __init__(self, max_per_signature: int = 10, phash_threshold: int = 4) -> None:
        """Initialize deduplication index.

        Args:
            max_per_signature: Maximum allowed tasks per identical structural signature (default 10).
            phash_threshold: Maximum Hamming distance for perceptual near-duplicate rejection (default 4).
        """
        self.max_per_signature = max_per_signature
        self.phash_threshold = phash_threshold
        self.signature_counts: dict[tuple, int] = defaultdict(int)
        self.kept_hashes: list[tuple[str, imagehash.ImageHash]] = []

    def check(self, task: Task, scene: Scene, image_path: Path | str) -> tuple[bool, str]:
        """Check whether a task is a structural or perceptual duplicate.

        Args:
            task: Task to check.
            scene: Corresponding scene model.
            image_path: Path to rendered/augmented task image.

        Returns:
            Tuple of (is_unique, failure_reason_if_any).
        """
        sig = structural_signature(task, scene)
        if self.signature_counts[sig] >= self.max_per_signature:
            return (
                False,
                f"structural_cap_exceeded: signature {sig} reached cap of {self.max_per_signature}",
            )

        task_hash = compute_phash(image_path)
        for existing_id, existing_hash in self.kept_hashes:
            dist = int(task_hash - existing_hash)
            if dist <= self.phash_threshold:
                return (
                    False,
                    f"perceptual_near_duplicate: phash distance {dist} <= {self.phash_threshold} to task '{existing_id}'",
                )

        return True, ""

    def add(self, task: Task, scene: Scene, image_path: Path | str) -> None:
        """Register an accepted task into the index."""
        sig = structural_signature(task, scene)
        self.signature_counts[sig] += 1
        task_hash = compute_phash(image_path)
        self.kept_hashes.append((task.task_id, task_hash))

    def check_and_add(self, task: Task, scene: Scene, image_path: Path | str) -> tuple[bool, str]:
        """Atomically check and add a task if unique."""
        is_unique, reason = self.check(task, scene, image_path)
        if is_unique:
            self.add(task, scene, image_path)
        return is_unique, reason

    def reset(self) -> None:
        """Clear all indexed signatures and hashes."""
        self.signature_counts.clear()
        self.kept_hashes.clear()


__all__ = ["DedupeIndex", "compute_phash", "structural_signature"]
