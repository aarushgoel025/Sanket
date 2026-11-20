"""End-to-end smoke test script for Sanket pipeline.

Generates 6 tasks (one per question type: DIRECT, BINDING, CLOSURE, OVERRIDE,
EGOCENTRIC, ABSENT), renders signboards via Playwright, applies deterministic
augmentations, performs independent dual-path verification, and queries OracleAdapter.

Exits with non-zero status on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from sanket.evaluate.adapters.fake import OracleAdapter
from sanket.evaluate.parser import parse_answer
from sanket.evaluate.scorer import score_single
from sanket.generator.augment import augment
from sanket.generator.renderer import render_scene
from sanket.generator.scene_builder import build_scene, sample_knobs
from sanket.graph.venue import load_venue
from sanket.questions.templates import make_task
from sanket.schema import Receipt, Task
from sanket.verify.fidelity import fidelity_ok
from sanket.verify.independent import independent_answer
from sanket.verify.visibility import visibility_ok

QUESTION_TYPES = ["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]


def run_smoke_test(out_dir: Path | str = "data/smoke_test") -> list[Task]:
    """Execute end-to-end generation, verification, and oracle evaluation across all 6 question types.

    Args:
        out_dir: Base directory for smoke test image and scene outputs.

    Returns:
        List of generated and validated Task models.

    Raises:
        RuntimeError: If any verification gate or oracle score fails.
    """
    base_path = Path(out_dir)
    images_dir = base_path / "images"
    scenes_dir = base_path / "scenes"
    images_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    venue_path = Path("config/venues/railway_station.yaml")
    venue = load_venue(venue_path)
    oracle = OracleAdapter()

    tasks: list[Task] = []
    print("=" * 70)
    print("SANKET END-TO-END SMOKE TEST (6 Question Types)")
    print("=" * 70)

    for idx, qtype in enumerate(QUESTION_TYPES, start=1):
        task_id = f"smoke_t{idx:02d}_{qtype.lower()}"
        seed = 42000 + idx * 101
        rng = np.random.default_rng(seed)

        # 1. Sample difficulty knobs and build scene
        knobs = sample_knobs(rng, qtype)
        sb = build_scene(venue, qtype, rng, knobs)

        # 2. Render to PNG and export DOM element geometry
        raw_png = images_dir / f"raw_{task_id}.png"
        geo = render_scene(sb.scene, venue, raw_png)

        # 3. Augment with pixel-level perturbations & transform geometry
        final_png = images_dir / f"{task_id}.png"
        aug_geo = augment(raw_png, geo, sb.scene.knobs, rng, final_png)
        raw_png.unlink(missing_ok=True)

        # 4. Save scene specification
        scene_path = scenes_dir / f"{task_id}.json"
        scene_path.write_text(sb.scene.model_dump_json(indent=2), encoding="utf-8")

        # 5. Assemble task
        task = make_task(
            sb=sb,
            venue=venue,
            rng=rng,
            task_id=task_id,
            seed=seed,
            image_path=str(final_png),
            scene_path=str(scene_path),
        )

        # 6. Independent Dual-Path Verification
        indep_ans = independent_answer(sb.scene, task)
        agree = indep_ans == task.gold
        if not agree:
            raise RuntimeError(
                f"[{task_id}] Dual-path mismatch: solver='{task.gold}', independent='{indep_ans}'"
            )

        fid_ok, fid_reason = fidelity_ok(sb.scene, aug_geo)
        if not fid_ok:
            raise RuntimeError(f"[{task_id}] Render fidelity check failed: {fid_reason}")

        vis_ok, vis_ratio = visibility_ok(sb.scene, task, aug_geo)
        if not vis_ok:
            raise RuntimeError(
                f"[{task_id}] Target visibility check failed (ratio={vis_ratio:.2f})."
            )

        task.receipt = Receipt(
            solver_answer=task.gold,
            independent_answer=indep_ans,
            agree=agree,
            fidelity_ok=fid_ok,
            visibility_ok=vis_ok,
            evidence_visible_ratio=vis_ratio,
            blind_correct_rate=0.0,
            blind_rejected=False,
            human_audit="unaudited",
            notes="smoke_test verification pass",
        )

        # 7. Evaluate with OracleAdapter
        raw_resp = oracle.answer(task, mode="image")
        parsed = parse_answer(raw_resp.text)
        correct = score_single(task, parsed)
        if not correct:
            raise RuntimeError(
                f"[{task_id}] Oracle evaluation failed: parsed='{parsed}', gold='{task.gold}'"
            )

        tasks.append(task)
        print(
            f"[{idx}/6] {qtype:11s} -> Gold: {task.gold:12s} | "
            f"Oracle: {parsed:12s} | Agree: {agree!s:5s} | Fid: {fid_ok!s:5s} | Vis: {vis_ok!s:5s} [PASS]"
        )

    print("=" * 70)
    print(
        f"SMOKE TEST SUCCESS: All {len(tasks)} tasks generated, verified, and scored 100% by Oracle."
    )
    print("=" * 70)
    return tasks


def main() -> int:
    """CLI entrypoint for smoke test."""
    try:
        run_smoke_test()
    except (RuntimeError, ValueError, OSError, FileNotFoundError) as exc:
        print(f"\n[!] SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
