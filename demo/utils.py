"""Shared utilities for Sanket Streamlit demo application.

Handles task loading, venue topology rendering with route highlighting,
model query execution through SQLite cache, and accessibility formatting.
"""

import itertools
import logging
import os
import tempfile
from collections import defaultdict
from pathlib import Path

# Ensure Matplotlib config directory is writable before importing matplotlib
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib.pyplot as plt
import networkx as nx
from pydantic import ValidationError

from sanket.evaluate.adapters.fake import AlwaysAdapter, OracleAdapter, RandomAdapter
from sanket.evaluate.cache import ResponseCache
from sanket.evaluate.parser import parse_answer
from sanket.graph.solver import build_graph, open_subgraph
from sanket.graph.venue import load_venue
from sanket.schema import Scene, Task, Venue

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TASKS_FILE = REPO_ROOT / "data" / "sample_tasks" / "tasks.jsonl"
FULL_TASKS_FILE = REPO_ROOT / "data" / "full_dataset" / "tasks.jsonl"
CACHE_FILE = REPO_ROOT / "data" / "cache" / "eval_cache.sqlite"
CONSEQUENCES_FILE = REPO_ROOT / "config" / "consequences.yaml"
VENUES_DIR = REPO_ROOT / "config" / "venues"


def get_venue_map() -> dict[str, Venue]:
    """Load all configured venues mapped by id and name."""
    venues: dict[str, Venue] = {}
    if VENUES_DIR.exists():
        for yaml_path in VENUES_DIR.glob("*.yaml"):
            try:
                v = load_venue(yaml_path)
                venues[v.id] = v
            except (OSError, ValueError, ValidationError) as exc:
                logger.debug("Could not load venue %s: %s", yaml_path, exc)
    return venues


def load_tasks(tasks_path: Path | str | None = None) -> list[Task]:
    """Load benchmark tasks from JSONL file with fallbacks."""
    if tasks_path is None or not Path(tasks_path).exists():
        if SAMPLE_TASKS_FILE.exists():
            tasks_path = SAMPLE_TASKS_FILE
        elif FULL_TASKS_FILE.exists():
            tasks_path = FULL_TASKS_FILE
        else:
            return []

    tasks: list[Task] = []
    path = Path(tasks_path)
    if not path.exists():
        return []

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                tasks.append(Task.model_validate_json(line))
            except (ValueError, ValidationError) as exc:
                logger.debug("Failed parsing task line: %s", exc)
    return tasks


def load_scene(scene_path: Path | str) -> Scene | None:
    """Load Scene model from JSON path."""
    p = Path(scene_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return None
    try:
        return Scene.model_validate_json(p.read_text(encoding="utf-8"))
    except (ValueError, ValidationError, OSError):
        return None


def get_minimal_pairs(tasks: list[Task]) -> dict[str, list[Task]]:
    """Group tasks into minimal counterfactual pairs."""
    pair_map: dict[str, list[Task]] = defaultdict(list)
    for t in tasks:
        if t.pair_id:
            pair_map[t.pair_id].append(t)

    # Sort each pair so 'a' comes before 'b'
    result: dict[str, list[Task]] = {}
    for pid, group in pair_map.items():
        if len(group) == 2:
            sorted_group = sorted(group, key=lambda x: 0 if x.pair_role == "a" else 1)
            result[pid] = sorted_group
    return result


def plot_venue_route(venue: Venue, task: Task, scene: Scene) -> plt.Figure:
    """Render venue topology graph with junction, target, and route path highlighted.

    Args:
        venue: Venue graph specification.
        task: Benchmark task with target_dest_id.
        scene: Active scene with junction_id.

    Returns:
        Matplotlib Figure object.
    """
    G = build_graph(venue)
    junction = scene.junction_id
    target_dest = task.target_dest_id

    # Determine shortest path if reachable
    route_edges: set[tuple[str, str]] = set()
    first_hop_edge: tuple[str, str] | None = None
    open_only = task.qtype != "CLOSURE"

    try:
        H = open_subgraph(G) if open_only else G
        paths = list(nx.all_shortest_paths(H, junction, target_dest, weight="length"))
        if paths:
            best_path = paths[0]
            if len(best_path) >= 2:
                first_hop_edge = (best_path[0], best_path[1])
            for u, v in itertools.pairwise(best_path):
                route_edges.add((u, v))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    pos = nx.spring_layout(G, seed=42, k=1.8 / (len(G.nodes) ** 0.5))

    # Node coloring and categorization
    node_colors = []
    node_sizes = []
    for node_id in G.nodes:
        if node_id == junction:
            node_colors.append("#F59E0B")  # Amber/Orange for viewer position
            node_sizes.append(900)
        elif node_id == target_dest:
            node_colors.append("#10B981")  # Green for target destination
            node_sizes.append(900)
        else:
            is_junc = any(n.id == node_id and n.kind == "junction" for n in venue.nodes)
            if is_junc:
                node_colors.append("#3B82F6")  # Blue for other junctions
                node_sizes.append(450)
            else:
                node_colors.append("#8B5CF6")  # Purple for other destinations
                node_sizes.append(450)

    # Draw regular edges
    closed_edge_set = set(scene.closed_edges) | {(v, u) for u, v in scene.closed_edges}
    base_edges = []
    closed_drawn_edges = []

    for u, v in G.edges:
        if (u, v) in closed_edge_set or (v, u) in closed_edge_set:
            closed_drawn_edges.append((u, v))
        elif (u, v) not in route_edges:
            base_edges.append((u, v))

    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=base_edges,
        ax=ax,
        edge_color="#CBD5E1",
        width=1.8,
        arrows=True,
        arrowsize=14,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.08",
    )

    if closed_drawn_edges:
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=closed_drawn_edges,
            ax=ax,
            edge_color="#EF4444",
            width=2.2,
            style="dashed",
            arrows=True,
            arrowsize=14,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.08",
        )

    # Draw highlighted route
    if route_edges:
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=list(route_edges),
            ax=ax,
            edge_color="#059669",
            width=3.8,
            arrows=True,
            arrowsize=20,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.08",
        )

    # Highlight first hop prominently
    if first_hop_edge:
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=[first_hop_edge],
            ax=ax,
            edge_color="#D97706",
            width=4.5,
            arrows=True,
            arrowsize=24,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.08",
        )

    # Draw nodes
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        edgecolors="#1E293B",
        linewidths=1.5,
    )

    # Labels: English names
    labels = {}
    for n in venue.nodes:
        if n.id in G.nodes:
            lbl = n.label.en.split("(")[0].strip()
            labels[n.id] = f"{lbl}\n[{n.id}]"

    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=8, font_family="sans-serif")

    # Legend
    legend_elements = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=f"Current Junction ({junction})",
            markerfacecolor="#F59E0B",
            markersize=11,
            markeredgecolor="#1E293B",
        ),
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=f"Target Destination ({target_dest})",
            markerfacecolor="#10B981",
            markersize=11,
            markeredgecolor="#1E293B",
        ),
        plt.Line2D(
            [0],
            [0],
            color="#D97706",
            lw=3,
            label="First Hop Direction (Gold Decision)",
        ),
        plt.Line2D(
            [0],
            [0],
            color="#059669",
            lw=3,
            label="Full Shortest Path",
        ),
    ]
    if closed_drawn_edges:
        legend_elements.append(
            plt.Line2D(
                [0], [0], color="#EF4444", lw=2, linestyle="--", label="Closed / Barricaded Edge"
            )
        )

    ax.legend(
        handles=legend_elements,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        frameon=True,
        facecolor="#FFFFFF",
        edgecolor="#E2E8F0",
        fontsize=8,
    )

    heading_text = f" (Heading {scene.heading}°)" if scene.heading is not None else ""
    ax.set_title(
        f"Venue Layout: {venue.name} | Observer at '{junction}'{heading_text} -> Target '{target_dest}'",
        fontsize=11,
        fontweight="bold",
        pad=12,
        color="#0F172A",
    )
    ax.axis("off")
    fig.tight_layout()
    return fig


def query_model(
    task: Task,
    model_name: str,
    mode: str = "image",
    prompt_version: str = "v1",
) -> tuple[str, bool, float, str, str]:
    """Execute model evaluation through cache and adapters.

    Args:
        task: Benchmark task to evaluate.
        model_name: Model identifier (oracle, random, always_ahead, gemini_flash, or_vision).
        mode: Evaluation mode ('image' or 'text').
        prompt_version: Benchmark prompt version template.

    Returns:
        Tuple of (parsed_answer, is_correct, latency_s, raw_text, source_tag).
    """
    cache = ResponseCache(CACHE_FILE)

    # 1. Check SQLite response cache first
    cached_resp = cache.get(
        model_id=model_name, task_id=task.task_id, mode=mode, prompt_version=prompt_version
    )
    if cached_resp is not None:
        parsed = parse_answer(cached_resp.text) or "PARSING_FAILED"
        is_correct = parsed == task.gold
        return parsed, is_correct, cached_resp.latency_s, cached_resp.text, "local_cache"

    # 2. Select appropriate adapter
    clean_name = model_name.strip().lower()

    if clean_name in ("oracle", "oracle_adapter"):
        adapter = OracleAdapter()
    elif clean_name in ("random", "random_baseline"):
        adapter = RandomAdapter(seed=task.seed)
    elif clean_name in ("always_ahead", "always_adapter", "always"):
        adapter = AlwaysAdapter(option="AHEAD")
    elif clean_name == "gemini_flash":
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            return (
                "NO_API_KEY",
                False,
                0.0,
                (
                    "GEMINI_API_KEY is not configured in environment or .env file.\n"
                    "Please configure an API key or use an offline fake adapter (Oracle, Random, Always AHEAD)."
                ),
                "error",
            )
        try:
            from sanket.evaluate.adapters.gemini import GeminiAdapter

            adapter = GeminiAdapter(model_id="gemini-2.5-flash")
        except (ImportError, ValueError, RuntimeError) as exc:
            return "ADAPTER_ERROR", False, 0.0, f"Failed initializing GeminiAdapter: {exc}", "error"
    elif clean_name == "or_vision":
        or_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not or_key:
            return (
                "NO_API_KEY",
                False,
                0.0,
                (
                    "OPENROUTER_API_KEY / OPENAI_API_KEY is not configured in environment or .env file.\n"
                    "Please configure an API key or use an offline fake adapter (Oracle, Random, Always AHEAD)."
                ),
                "error",
            )
        try:
            from sanket.evaluate.adapters.openai_compat import OpenAICompatAdapter

            adapter = OpenAICompatAdapter(
                model_id="google/gemini-2.5-flash",
                base_url="https://openrouter.ai/api/v1",
                api_key=or_key,
            )
        except (ImportError, ValueError, RuntimeError) as exc:
            return (
                "ADAPTER_ERROR",
                False,
                0.0,
                f"Failed initializing OpenAICompatAdapter: {exc}",
                "error",
            )
    else:
        adapter = RandomAdapter(seed=task.seed)

    # 3. Call adapter and store response in cache
    try:
        raw_resp = adapter.answer(task=task, mode=mode, prompt_version=prompt_version)
        cache.set(
            model_id=model_name,
            task_id=task.task_id,
            mode=mode,
            prompt_version=prompt_version,
            raw_text=raw_resp.text,
            latency_s=raw_resp.latency_s,
            meta=raw_resp.meta,
        )
        parsed = parse_answer(raw_resp.text) or "PARSING_FAILED"
        is_correct = parsed == task.gold
        return parsed, is_correct, raw_resp.latency_s, raw_resp.text, "live_query"
    except (ValueError, RuntimeError, OSError) as exc:
        return "QUERY_FAILED", False, 0.0, f"Evaluation query encountered error: {exc}", "error"


__all__ = [
    "CACHE_FILE",
    "CONSEQUENCES_FILE",
    "FULL_TASKS_FILE",
    "SAMPLE_TASKS_FILE",
    "VENUES_DIR",
    "get_minimal_pairs",
    "get_venue_map",
    "load_scene",
    "load_tasks",
    "plot_venue_route",
    "query_model",
]
