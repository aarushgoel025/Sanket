"""Dataset generation pipeline orchestrator.

Coordinates scene generation, rendering, augmentation, verification,
filtering, pair construction, and dataset export to data/full_dataset/.
"""

import hashlib
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from sanket.config import DefaultConfig, load_default_config
from sanket.generator.augment import augment
from sanket.generator.renderer import _get_browser_executable, render_scene
from sanket.generator.scene_builder import RejectScene, build_scene, sample_knobs
from sanket.graph.solver import AmbiguousRoute, gold_answer
from sanket.graph.venue import load_venue
from sanket.questions.templates import make_task
from sanket.schema import ANSWER_OPTIONS, Scene, Task, Venue
from sanket.verify.blind_test import FakeBlindAdapter, run_blind_test
from sanket.verify.dedupe import DedupeIndex
from sanket.verify.fidelity import fidelity_ok
from sanket.verify.independent import independent_answer
from sanket.verify.pairs import build_minimal_pair
from sanket.verify.receipt import build_receipt
from sanket.verify.visibility import visibility_ok

logger = logging.getLogger(__name__)

QUESTION_TYPES = ["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]


def derive_task_seed(master_seed: int, index: int) -> int:
    """Deterministically derive a 32-bit seed from master_seed and task index."""
    raw = hashlib.sha256(f"{master_seed}:{index}".encode()).digest()
    return int.from_bytes(raw[:4], "little")


def build_dataset(
    out_dir: Path | str = "data/full_dataset",
    n_keep: int | None = None,
    total_tasks: int | None = None,
    master_seed: int | None = None,
    config_path: Path | str | None = None,
    venue_paths: list[Path | str] | None = None,
    blind_adapter: Any = None,
    browser: Any = None,
) -> dict[str, Any]:
    """Execute the full benchmark generation and verification pipeline.

    Order of operations:
    1. Sample knobs, build scenes, render, augment, make tasks.
    2. Verification layers: solver, independent, fidelity, visibility, dedupe.
    3. Blind test on survivors.
    4. Balance gold answers (<= 25% share within question type).
    5. Construct minimal counterfactual pairs for pair_fraction of kept tasks.
    6. Serialize images, scene specifications, tasks.jsonl, rejected.jsonl, build_stats.json.

    Args:
        out_dir: Output directory path.
        n_keep: Target number of validated tasks to keep (overrides config).
        total_tasks: Total tasks to attempt to generate (overrides config).
        master_seed: Root seed for deterministic generation.
        config_path: Optional path to default.yaml configuration.
        venue_paths: Optional list of venue YAML files to sample from.
        blind_adapter: Optional model adapter for blind language bias test.
        browser: Optional running Playwright Browser instance.

    Returns:
        Dictionary summarizing dataset build statistics.
    """
    out_dir = Path(out_dir)
    images_dir = out_dir / "images"
    scenes_dir = out_dir / "scenes"
    images_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    cfg: DefaultConfig = load_default_config(config_path)

    seed_master = master_seed if master_seed is not None else cfg.master_seed
    target_keep = n_keep if n_keep is not None else cfg.keep_tasks
    if total_tasks is not None:
        total_to_generate = total_tasks
    elif n_keep is not None:
        total_to_generate = max(target_keep, int(np.ceil(target_keep * 1.8)))
    else:
        total_to_generate = cfg.total_tasks

    # Load venue layouts
    if venue_paths:
        venues = [load_venue(p) for p in venue_paths]
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        v_rail = repo_root / "config" / "venues" / "railway_station.yaml"
        v_hosp = repo_root / "config" / "venues" / "hospital.yaml"
        venues = [load_venue(v_rail), load_venue(v_hosp)]

    # Setup shared browser if not supplied
    managed_browser = False
    playwright_context = None
    if browser is None:
        try:
            from playwright.sync_api import sync_playwright

            playwright_context = sync_playwright().start()
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
            browser = playwright_context.chromium.launch(**launch_args)
            managed_browser = True
        except (RuntimeError, OSError, ImportError) as exc:
            logger.debug("Could not launch shared browser: %s", exc)
            browser = None

    if blind_adapter is None:
        blind_adapter = FakeBlindAdapter(mode="random", rng=np.random.default_rng(seed_master))

    rejected_records: list[dict[str, Any]] = []
    rejected_counts: dict[str, int] = defaultdict(int)

    def record_rejection(
        task_id: str, seed: int, qtype: str, reason: str, details: str = ""
    ) -> None:
        rejected_records.append(
            {
                "task_id": task_id,
                "seed": seed,
                "qtype": qtype,
                "reason": reason,
                "details": details,
            }
        )
        rejected_counts[reason] += 1

    dedupe_index = DedupeIndex(max_per_signature=10, phash_threshold=4)
    stage1_survivors: list[tuple[Task, Scene, Venue, Path]] = []

    try:
        # Step 1 & 2: Generation and verification layers
        for idx in range(total_to_generate):
            task_seed = derive_task_seed(seed_master, idx)
            qtype = QUESTION_TYPES[idx % len(QUESTION_TYPES)]
            venue = venues[idx % len(venues)]
            task_id = f"task_{idx:04d}"

            rng = np.random.default_rng(task_seed)
            knobs = sample_knobs(rng, qtype)

            try:
                sb = build_scene(venue, qtype, rng, knobs)
            except (RejectScene, AmbiguousRoute, ValueError) as exc:
                record_rejection(task_id, task_seed, qtype, "ambiguous_route", str(exc))
                continue

            raw_png = images_dir / f"{task_id}_raw.png"
            final_png = images_dir / f"{task_id}.png"
            scene_path = scenes_dir / f"{task_id}.json"

            # Render DOM
            try:
                geo = render_scene(sb.scene, venue, raw_png, browser=browser)
            except (RuntimeError, OSError, ValueError) as exc:
                raw_png.unlink(missing_ok=True)
                record_rejection(
                    task_id, task_seed, qtype, "fidelity_fail", f"Render crashed: {exc}"
                )
                continue

            # Render fidelity check
            fid_ok, fid_reason = fidelity_ok(sb.scene, geo)
            if not fid_ok:
                raw_png.unlink(missing_ok=True)
                record_rejection(task_id, task_seed, qtype, "fidelity_fail", fid_reason)
                continue

            # Augmentation
            try:
                trans_geo = augment(
                    raw_png, geo, sb.scene.knobs, np.random.default_rng(task_seed), final_png
                )
                raw_png.unlink(missing_ok=True)
            except (RuntimeError, OSError, ValueError) as exc:
                raw_png.unlink(missing_ok=True)
                final_png.unlink(missing_ok=True)
                record_rejection(
                    task_id, task_seed, qtype, "visibility_fail", f"Augment failed: {exc}"
                )
                continue

            # Task construction
            task = make_task(
                sb=sb,
                venue=venue,
                rng=np.random.default_rng(task_seed),
                task_id=task_id,
                seed=task_seed,
                image_path=str(final_png),
                scene_path=str(scene_path),
            )

            # Solver vs independent agreement
            try:
                solver_ans = gold_answer(
                    venue=venue,
                    closed_edges=sb.scene.closed_edges,
                    junction=sb.scene.junction_id,
                    heading=sb.scene.heading,
                    dest=sb.target_dest_id,
                    turn_cw=task.turn_cw,
                    listed=(qtype != "ABSENT"),
                )
            except (AmbiguousRoute, ValueError, KeyError) as exc:
                final_png.unlink(missing_ok=True)
                record_rejection(
                    task_id, task_seed, qtype, "ambiguous_route", f"Solver failed: {exc}"
                )
                continue

            indep_ans = independent_answer(sb.scene, task)
            if solver_ans != indep_ans or solver_ans != task.gold:
                final_png.unlink(missing_ok=True)
                record_rejection(
                    task_id,
                    task_seed,
                    qtype,
                    "solver_independent_mismatch",
                    f"solver={solver_ans}, indep={indep_ans}, gold={task.gold}",
                )
                continue

            # Visibility check
            vis_ok, vis_ratio = visibility_ok(sb.scene, task, trans_geo)
            if not vis_ok:
                final_png.unlink(missing_ok=True)
                record_rejection(
                    task_id,
                    task_seed,
                    qtype,
                    "visibility_fail",
                    f"visibility failed with mean ratio {vis_ratio}",
                )
                continue

            # Build receipt
            task.receipt = build_receipt(
                task=task,
                scene=sb.scene,
                solver_answer=solver_ans,
                independent_answer=indep_ans,
                fidelity=(fid_ok, fid_reason),
                visibility=(vis_ok, vis_ratio),
            )

            # Deduplication check
            unique_ok, dedupe_reason = dedupe_index.check_and_add(task, sb.scene, final_png)
            if not unique_ok:
                final_png.unlink(missing_ok=True)
                record_rejection(task_id, task_seed, qtype, "duplicate", dedupe_reason)
                continue

            stage1_survivors.append((task, sb.scene, venue, final_png))

        # Step 3: Blind test on survivors
        stage2_survivors: list[tuple[Task, Scene, Venue, Path]] = []
        for task, scene, venue, img_p in stage1_survivors:
            blind_ok, blind_rate, _ = run_blind_test(
                task=task,
                adapter=blind_adapter,
                samples=cfg.blind_samples,
                threshold=cfg.blind_threshold,
            )
            if not blind_ok:
                img_p.unlink(missing_ok=True)
                record_rejection(
                    task.task_id,
                    task.seed,
                    task.qtype,
                    "blind_test_fail",
                    f"blind_rate={blind_rate} >= {cfg.blind_threshold}",
                )
                continue
            stage2_survivors.append((task, scene, venue, img_p))

        # Step 4: Balance gold answers (<= 25% share within each type)
        type_survivors: dict[str, list[tuple[Task, Scene, Venue, Path]]] = defaultdict(list)
        for t, s, v, p in stage2_survivors:
            type_survivors[t.qtype].append((t, s, v, p))

        target_per_type = max(1, target_keep // len(QUESTION_TYPES))
        max_per_gold = max(1, int(np.ceil(target_per_type * 0.25)))

        balanced_tasks: list[tuple[Task, Scene, Venue, Path]] = []
        for qtype in QUESTION_TYPES:
            candidates = type_survivors.get(qtype, [])
            gold_counts: dict[str, int] = defaultdict(int)
            kept_for_type: list[tuple[Task, Scene, Venue, Path]] = []

            for t, s, v, p in candidates:
                if len(kept_for_type) >= target_per_type:
                    break
                # Balancing across 10 options applies as far as the graph allows (directional types)
                if qtype not in ("ABSENT", "CLOSURE") and gold_counts[t.gold] >= max_per_gold:
                    p.unlink(missing_ok=True)
                    record_rejection(
                        t.task_id,
                        t.seed,
                        t.qtype,
                        "imbalanced",
                        f"gold '{t.gold}' reached 25% cap ({max_per_gold}) for type '{qtype}'",
                    )
                    continue

                gold_counts[t.gold] += 1
                kept_for_type.append((t, s, v, p))

            balanced_tasks.extend(kept_for_type)

        # Truncate to exact target_keep if over
        final_kept: list[tuple[Task, Scene, Venue, Path]] = balanced_tasks[:target_keep]

        # Step 5: Minimal counterfactual pairs
        pairs_built_count = 0
        num_pairs_to_attempt = max(1, round(len(final_kept) * cfg.pair_fraction))
        pair_additions: list[tuple[Task, Scene, Venue, Path]] = []

        qtype_gold_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        qtype_totals: dict[str, int] = defaultdict(int)
        for t, _, _, _ in final_kept:
            qtype_gold_counts[t.qtype][t.gold] += 1
            qtype_totals[t.qtype] += 1

        for idx, (t_a, s_a, v_a, p_a) in enumerate(final_kept):
            if pairs_built_count >= num_pairs_to_attempt:
                break

            # Respect 25% balance limit within directional types
            allowed_gold: set[str] | None = None
            if t_a.qtype in ("DIRECT", "BINDING", "OVERRIDE", "EGOCENTRIC"):
                new_total = qtype_totals[t_a.qtype] + 1
                max_allowed = max(2, int(np.ceil(new_total * 0.25)))
                allowed_gold = {
                    ans for ans in ANSWER_OPTIONS if qtype_gold_counts[t_a.qtype][ans] < max_allowed
                }

            pair_result = build_minimal_pair(
                task_a=t_a,
                scene_a=s_a,
                venue=v_a,
                image_a_path=p_a,
                out_images_dir=images_dir,
                out_scenes_dir=scenes_dir,
                browser=browser,
                allowed_gold=allowed_gold,
            )
            if pair_result is not None:
                updated_t_a, t_b, s_b, p_b = pair_result
                final_kept[idx] = (updated_t_a, s_a, v_a, p_a)
                pair_additions.append((t_b, s_b, v_a, p_b))
                pairs_built_count += 1
                qtype_gold_counts[t_b.qtype][t_b.gold] += 1
                qtype_totals[t_b.qtype] += 1

        all_final_tasks = final_kept + pair_additions

        # Step 6: Output serialization
        # Write scenes
        for task, scene, _, _ in all_final_tasks:
            sc_path = scenes_dir / f"{task.task_id}.json"
            task.scene_path = str(sc_path)
            with open(sc_path, "w", encoding="utf-8") as f:
                f.write(scene.model_dump_json(indent=2))

        # Write tasks.jsonl deterministically sorted
        tasks_file = out_dir / "tasks.jsonl"
        with open(tasks_file, "w", encoding="utf-8") as f:
            for task, _, _, _ in sorted(all_final_tasks, key=lambda x: x[0].task_id):
                f.write(task.model_dump_json() + "\n")

        # Write rejected.jsonl
        rejected_file = out_dir / "rejected.jsonl"
        with open(rejected_file, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, sort_keys=True) + "\n" for r in rejected_records)

        # Compile build stats
        per_type_counts: dict[str, int] = defaultdict(int)
        for task, _, _, _ in all_final_tasks:
            per_type_counts[task.qtype] += 1

        stats: dict[str, Any] = {
            "master_seed": seed_master,
            "total_generated": total_to_generate,
            "total_kept": len(all_final_tasks),
            "rejected_by_reason": dict(rejected_counts),
            "per_type_counts": dict(per_type_counts),
            "pairs_built": pairs_built_count,
        }

        stats_file = out_dir / "build_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, sort_keys=True)

        return stats

    finally:
        if managed_browser and browser is not None:
            browser.close()
        if playwright_context is not None:
            playwright_context.stop()


__all__ = ["build_dataset", "derive_task_seed"]
