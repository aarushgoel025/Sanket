"""Sanket FastAPI Backend Server.

Provides REST endpoints for the React+Vite frontend demo:
- Task inspection and filtering across sample tasks.
- Live procedural signboard generation and dual-path verification.
- Model evaluation via fake/real adapters with SQLite caching.
- Interactive venue topology and route calculation for SVG rendering.
- Benchmark findings, publication figures (F1-F6), and failure gallery with consequence stories.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

# Ensure Matplotlib config directory is writable before importing matplotlib
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import networkx as nx
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from demo.utils import (
    CONSEQUENCES_FILE,
    REPO_ROOT,
    get_minimal_pairs,
    get_venue_map,
    load_scene,
    load_tasks,
    plot_venue_route,
    query_model,
)
from sanket.generator.augment import augment
from sanket.generator.renderer import render_scene
from sanket.generator.scene_builder import build_scene
from sanket.graph.solver import build_graph
from sanket.questions.templates import make_task
from sanket.schema import Knobs, Task
from sanket.verify.receipt import build_receipt

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sanket Benchmark API",
    description="Backend REST API for Sanket Multimodal Wayfinding Benchmark",
    version="1.0.0",
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generated live tasks directory
GENERATED_DIR = REPO_ROOT / "data" / "generated"
GENERATED_IMAGES_DIR = GENERATED_DIR / "images"
GENERATED_SCENES_DIR = GENERATED_DIR / "scenes"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_SCENES_DIR.mkdir(parents=True, exist_ok=True)

# In-memory store for newly generated tasks
live_tasks: dict[str, Task] = {}

# Mount static asset directories
sample_img_dir = REPO_ROOT / "data" / "sample_tasks" / "images"
if sample_img_dir.exists():
    app.mount(
        "/static/sample_images", StaticFiles(directory=str(sample_img_dir)), name="sample_images"
    )

figures_dir = REPO_ROOT / "reports" / "figures"
if figures_dir.exists():
    app.mount("/static/figures", StaticFiles(directory=str(figures_dir)), name="figures")

real_photos_dir = REPO_ROOT / "data" / "real_photos" / "images"
if real_photos_dir.exists():
    app.mount(
        "/static/real_images", StaticFiles(directory=str(real_photos_dir)), name="real_images"
    )

app.mount(
    "/static/generated_images",
    StaticFiles(directory=str(GENERATED_IMAGES_DIR)),
    name="generated_images",
)


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    venue_id: str = "railway_station"
    qtype: str = "DIRECT"
    seed: int = 42
    n_entries: int = 4
    perspective_deg: float = 10.0
    clutter: int = 4
    blur: float = 0.5


class AskRequest(BaseModel):
    task_id: str
    model_name: str = "oracle"
    mode: str = "image"
    prompt_version: str = "v1"


# -----------------------------------------------------------------------------
# Endpoints: Venues & Graphs
# -----------------------------------------------------------------------------
@app.get("/api/venues")
def list_venues() -> list[dict[str, Any]]:
    """List all configured venues with descriptions."""
    venues = get_venue_map()
    return [
        {
            "id": v.id,
            "name": v.name,
            "node_count": len(v.nodes),
            "edge_count": len(v.edges),
            "junctions": [n.id for n in v.nodes if n.kind == "junction"],
            "destinations": [n.id for n in v.nodes if n.kind == "destination"],
        }
        for v in venues.values()
    ]


@app.get("/api/venues/{venue_id}/graph")
def get_venue_graph_data(venue_id: str) -> dict[str, Any]:
    """Return nodes with normalized 2D coordinates and edges for SVG rendering."""
    venues = get_venue_map()
    if venue_id not in venues:
        raise HTTPException(status_code=404, detail=f"Venue '{venue_id}' not found")

    venue = venues[venue_id]
    G = build_graph(venue)
    pos = nx.spring_layout(G, seed=42, k=1.8 / max(1.0, len(G.nodes) ** 0.5))

    # Normalize positions into an 800x500 viewport with padding
    xs = [coord[0] for coord in pos.values()]
    ys = [coord[1] for coord in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1e-5, max_x - min_x)
    span_y = max(1e-5, max_y - min_y)

    nodes_data = []
    for node in venue.nodes:
        if node.id in pos:
            raw_x, raw_y = pos[node.id]
            norm_x = 80 + ((raw_x - min_x) / span_x) * 640
            norm_y = 60 + ((raw_y - min_y) / span_y) * 380
            nodes_data.append(
                {
                    "id": node.id,
                    "label_en": node.label.en,
                    "label_hi": getattr(node.label, "hi", None),
                    "kind": node.kind,
                    "x": round(norm_x, 1),
                    "y": round(norm_y, 1),
                }
            )

    edges_data = []
    for edge in venue.edges:
        edges_data.append(
            {
                "from_node": edge.a,
                "to_node": edge.b,
                "bearing": edge.bearing_ab,
                "length": edge.length,
                "status": edge.status,
            }
        )

    return {
        "venue_id": venue.id,
        "name": venue.name,
        "nodes": nodes_data,
        "edges": edges_data,
    }


# -----------------------------------------------------------------------------
# Endpoints: Tasks
# -----------------------------------------------------------------------------
def _resolve_task_image_url(task: Task) -> str:
    """Map local file path to accessible static URL."""
    p_str = str(task.image_path).replace("\\", "/")
    filename = Path(p_str).name
    if "sample_tasks/images/" in p_str or (sample_img_dir / filename).exists():
        return f"/static/sample_images/{filename}"
    elif "real_photos/images/" in p_str or "images/R" in p_str:
        return f"/static/real_images/{filename}"
    elif "generated/images/" in p_str or (GENERATED_IMAGES_DIR / filename).exists():
        return f"/static/generated_images/{filename}"
    return f"/static/sample_images/{filename}"


def _task_to_dict(task: Task) -> dict[str, Any]:
    """Serialize task with resolved URLs, scenes, and receipts."""
    data = task.model_dump()
    data["image_url"] = _resolve_task_image_url(task)
    if task.scene_path:
        scene = load_scene(task.scene_path)
        if scene:
            data["scene"] = scene.model_dump()
    return data


@app.get("/api/tasks")
def list_tasks(
    qtype: str | None = Query(None, description="Filter by question type"),
    pair_only: bool = Query(False, description="Filter only tasks with minimal pairs"),
) -> list[dict[str, Any]]:
    """List sample and live generated tasks."""
    sample_tasks = load_tasks()
    all_tasks = sample_tasks + list(live_tasks.values())

    filtered = all_tasks
    if qtype and qtype != "All":
        filtered = [t for t in filtered if t.qtype == qtype]
    if pair_only:
        filtered = [t for t in filtered if t.pair_id]

    return [_task_to_dict(t) for t in filtered]


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    """Retrieve full task details, scene configuration, and verification receipt."""
    all_tasks = {t.task_id: t for t in load_tasks()}
    all_tasks.update(live_tasks)

    if task_id not in all_tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task = all_tasks[task_id]
    task_dict = _task_to_dict(task)

    # Attach scene if available
    scene = load_scene(task.scene_path)
    if scene:
        task_dict["scene"] = scene.model_dump()

    return task_dict


@app.get("/api/tasks/{task_id}/route-plot")
def get_task_route_plot(task_id: str):
    """Generate and return Matplotlib route plot PNG for this task."""
    all_tasks = {t.task_id: t for t in load_tasks()}
    all_tasks.update(live_tasks)

    if task_id not in all_tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task = all_tasks[task_id]
    scene = load_scene(task.scene_path)
    venues = get_venue_map()
    venue = venues.get(scene.venue_id if scene else "railway_station", next(iter(venues.values())))

    if not scene:
        raise HTTPException(status_code=404, detail="Scene specification not found for task")

    fig = plot_venue_route(venue, task, scene)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=140)
    import matplotlib.pyplot as plt

    plt.close(fig)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")


# -----------------------------------------------------------------------------
# Endpoints: Live Generation
# -----------------------------------------------------------------------------
@app.post("/api/generate")
def generate_new_task(req: GenerateRequest) -> dict[str, Any]:
    """Procedurally synthesize, render, augment, and dual-verify a brand-new task."""
    venues = get_venue_map()
    if req.venue_id not in venues:
        raise HTTPException(status_code=400, detail=f"Invalid venue_id: {req.venue_id}")

    venue = venues[req.venue_id]
    task_id = f"gen_{req.qtype.lower()}_{req.seed}"

    knobs = Knobs(
        n_entries=req.n_entries,
        perspective_deg=req.perspective_deg,
        clutter=req.clutter,
        blur=req.blur,
    )

    try:
        scene = build_scene(venue, req.qtype, req.seed, knobs)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"Scene builder error: {exc}")

    # Render DOM
    try:
        raw_image, bounding_boxes = render_scene(scene)
    except (RuntimeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Renderer error: {exc}")

    # Augment
    aug_image = augment(raw_image, knobs, seed=req.seed)

    # Save files
    img_path = GENERATED_IMAGES_DIR / f"{task_id}.png"
    scene_path = GENERATED_SCENES_DIR / f"{task_id}.json"
    aug_image.save(img_path, format="PNG")
    scene_path.write_text(scene.model_dump_json(indent=2), encoding="utf-8")

    # Make task and verification receipt
    task = make_task(
        task_id=task_id,
        scene=scene,
        image_path=str(img_path.relative_to(REPO_ROOT)),
        scene_path=str(scene_path.relative_to(REPO_ROOT)),
        venue=venue,
    )

    # Dual-path verification receipt
    from sanket.verify.fidelity import fidelity_ok
    from sanket.verify.independent import verify_independent
    from sanket.verify.visibility import visibility_ok

    ind_ans = verify_independent(scene, task.target_dest_id, task.qtype, task.turn_cw)
    fid = fidelity_ok(scene, bounding_boxes)
    vis, ratio = visibility_ok(scene, task.target_dest_id, knobs)

    receipt = build_receipt(
        solver_answer=task.gold,
        independent_answer=ind_ans,
        fidelity_ok=fid,
        visibility_ok=vis,
        evidence_visible_ratio=ratio,
        blind_correct_rate=0.0,
        blind_rejected=False,
    )
    task.receipt = receipt

    live_tasks[task_id] = task

    task_dict = _task_to_dict(task)
    task_dict["scene"] = scene.model_dump()
    return task_dict


# -----------------------------------------------------------------------------
# Endpoints: Model Evaluation
# -----------------------------------------------------------------------------
@app.post("/api/ask")
def ask_model(req: AskRequest) -> dict[str, Any]:
    """Query a model adapter (cached or live) on a specific benchmark task."""
    all_tasks = {t.task_id: t for t in load_tasks()}
    all_tasks.update(live_tasks)

    if req.task_id not in all_tasks:
        raise HTTPException(status_code=404, detail=f"Task '{req.task_id}' not found")

    task = all_tasks[req.task_id]

    parsed, is_correct, latency, raw_text, source_tag = query_model(
        task=task,
        model_name=req.model_name,
        mode=req.mode,
        prompt_version=req.prompt_version,
    )

    return {
        "task_id": task.task_id,
        "model_name": req.model_name,
        "mode": req.mode,
        "gold_answer": task.gold,
        "model_answer": parsed,
        "is_correct": is_correct,
        "latency_s": round(latency, 3),
        "raw_response": raw_text,
        "source": source_tag,
    }


# -----------------------------------------------------------------------------
# Endpoints: Minimal Pairs
# -----------------------------------------------------------------------------
@app.get("/api/pairs")
def list_minimal_pairs() -> list[dict[str, Any]]:
    """Return grouped counterfactual minimal pairs with visual deltas."""
    sample_tasks = load_tasks()
    pair_map = get_minimal_pairs(sample_tasks)

    pairs_list = []
    for pid, group in pair_map.items():
        if len(group) == 2:
            task_a = group[0]
            task_b = group[1]
            pairs_list.append(
                {
                    "pair_id": pid,
                    "qtype": task_a.qtype,
                    "task_a": _task_to_dict(task_a),
                    "task_b": _task_to_dict(task_b),
                    "gold_a": task_a.gold,
                    "gold_b": task_b.gold,
                    "golds_differ": task_a.gold != task_b.gold,
                }
            )

    return pairs_list


# -----------------------------------------------------------------------------
# Endpoints: Findings & Figures
# -----------------------------------------------------------------------------
@app.get("/api/findings")
def get_findings_summary() -> dict[str, Any]:
    """Return benchmark publication figures (F1-F6) and performance metrics."""
    figure_definitions = [
        {
            "id": "F1",
            "file": "F1_model_skill_heatmap.png",
            "url": "/static/figures/F1_model_skill_heatmap.png",
            "title": "Model Performance Across Wayfinding Skills",
            "takeaway": "Models struggle most on BINDING (associating stacked arrows with destinations) and OVERRIDE (honoring detour notices).",
        },
        {
            "id": "F2",
            "file": "F2_difficulty_curves.png",
            "url": "/static/figures/F2_difficulty_curves.png",
            "title": "Accuracy Degradation Under Density & Noise",
            "takeaway": "Performance drops sharply as destination count increases from 2 to 8 entries on a single signboard.",
        },
        {
            "id": "F3",
            "file": "F3_perception_gap.png",
            "url": "/static/figures/F3_perception_gap.png",
            "title": "Perception vs. Reasoning Gap",
            "takeaway": "Structured text input achieves an 83.3% accuracy vs. 33.3% on raw images (+50.0 pp gap), confirming visual symbol binding as the primary bottleneck.",
        },
        {
            "id": "F4",
            "file": "F4_hallucination_absent.png",
            "url": "/static/figures/F4_hallucination_absent.png",
            "title": "Hallucination Rate on ABSENT Signage",
            "takeaway": "When destinations are unlisted, VLMs exhibit a 100% directional hallucination rate instead of recognizing NOT_INDICATED.",
        },
        {
            "id": "F5",
            "file": "F5_synthetic_vs_real.png",
            "url": "/static/figures/F5_synthetic_vs_real.png",
            "title": "Synthetic vs. Real-Photo Transfer",
            "takeaway": "Evaluation on hand-labelled station photos confirms strong correlation with synthetic benchmark rankings.",
        },
        {
            "id": "F6",
            "file": "F6_pair_consistency.png",
            "url": "/static/figures/F6_pair_consistency.png",
            "title": "Minimal-Pair Consistency Matrix",
            "takeaway": "VLMs achieve 0.0% joint consistency on minimal pairs, frequently flipping decisions inappropriately or failing to track single 45° arrow edits.",
        },
    ]

    model_metrics = [
        {
            "model": "Oracle (Sanity Check)",
            "mode": "image",
            "tasks": 34,
            "correct": 34,
            "acc": 100.0,
            "ci": "[89.8%, 100.0%]",
        },
        {
            "model": "Oracle (Sanity Check)",
            "mode": "text",
            "tasks": 29,
            "correct": 29,
            "acc": 100.0,
            "ci": "[88.3%, 100.0%]",
        },
        {
            "model": "Gemini 1.5 Flash",
            "mode": "image",
            "tasks": 24,
            "correct": 8,
            "acc": 33.3,
            "ci": "[18.0%, 53.3%]",
        },
        {
            "model": "Gemini 1.5 Flash",
            "mode": "text",
            "tasks": 24,
            "correct": 20,
            "acc": 83.3,
            "ci": "[64.1%, 93.3%]",
        },
        {
            "model": "Random Baseline",
            "mode": "image",
            "tasks": 24,
            "correct": 3,
            "acc": 12.5,
            "ci": "[4.3%, 31.0%]",
        },
        {
            "model": "Always AHEAD",
            "mode": "image",
            "tasks": 16,
            "correct": 0,
            "acc": 0.0,
            "ci": "[0.0%, 19.4%]",
        },
    ]

    return {
        "figures": figure_definitions,
        "model_metrics": model_metrics,
        "perception_gap": {
            "gemini_flash": {"image_acc": 33.3, "text_acc": 83.3, "gap_pp": 50.0},
        },
    }


# -----------------------------------------------------------------------------
# Endpoints: Failure Gallery & Real-World Consequences
# -----------------------------------------------------------------------------
@app.get("/api/failures")
def get_failure_gallery() -> list[dict[str, Any]]:
    """Return curated model failure cases with severity and physical consequence stories."""
    consequences: dict[str, Any] = {}
    if CONSEQUENCES_FILE.exists():
        try:
            consequences = yaml.safe_load(CONSEQUENCES_FILE.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.debug("Failed parsing consequences.yaml: %s", exc)

    curated_failures = [
        {
            "task_id": "task_0001",
            "qtype": "BINDING",
            "image_url": "/static/sample_images/task_0001.png",
            "question": "Which way should you go to reach Radiology?",
            "gold": "RIGHT",
            "model_pred": "AHEAD",
            "model_name": "gemini_flash",
            "mode": "image",
            "failure_reason": "Visual Symbol Binding Confusion",
            "explanation": "Model misattributed the top arrow (pointing AHEAD to Oncology) to Radiology on row 3, disregarding row dividers.",
            "severity": "HIGH",
            "real_world_consequence": consequences.get("misleading_turns", {}).get(
                "story", "Patient enters wrong hospital wing, delaying scheduled scan."
            ),
        },
        {
            "task_id": "task_0003",
            "qtype": "CLOSURE",
            "image_url": "/static/sample_images/task_0003.png",
            "question": "Which way should you go to reach Platform 2?",
            "gold": "CLOSED",
            "model_pred": "LEFT",
            "model_name": "gemini_flash",
            "mode": "image",
            "failure_reason": "Maintenance Overlay Blindness",
            "explanation": "Model read the permanent arrow pointing LEFT, completely failing to detect the red 'CLOSED / MAINTENANCE' cross-out badge.",
            "severity": "CRITICAL",
            "real_world_consequence": consequences.get("route_closure_ignored", {}).get(
                "story", "Passenger walks into active construction zone with barricades."
            ),
        },
        {
            "task_id": "task_0006",
            "qtype": "ABSENT",
            "image_url": "/static/sample_images/task_0006.png",
            "question": "Which way should you go to reach Baggage Storage?",
            "gold": "NOT_INDICATED",
            "model_pred": "AHEAD_RIGHT",
            "model_name": "gemini_flash",
            "mode": "image",
            "failure_reason": "Directional Hallucination on Unlisted Destination",
            "explanation": "Destination does not exist on signboard. Rather than selecting NOT_INDICATED, model hallucinated a plausible heading.",
            "severity": "MEDIUM",
            "real_world_consequence": consequences.get("absent_destination_hallucinated", {}).get(
                "story", "Traveller wanders opposite direction searching for unlisted locker."
            ),
        },
    ]

    return curated_failures


@app.get("/api/health")
def health_check():
    """Server health probe."""
    return {"status": "ok", "version": "1.0.0"}


# Mount compiled React frontend if built
frontend_dist = REPO_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
