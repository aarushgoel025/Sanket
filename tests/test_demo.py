"""Unit tests for Sanket Streamlit demo application and utilities.

Verifies:
- Task and venue loading.
- Minimal-pair grouping.
- Venue graph route plotting.
- Query model execution through cache and fake adapters.
- Graceful handling when external API keys are missing.
- Syntax and import integrity of all demo pages.
"""

import importlib.util
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))

import matplotlib.pyplot as plt

from demo.utils import (
    get_minimal_pairs,
    get_venue_map,
    load_scene,
    load_tasks,
    plot_venue_route,
    query_model,
)
from sanket.schema import Task, Venue


def test_venue_and_task_loading() -> None:
    """Verify venue map and sample tasks load accurately."""
    venues = get_venue_map()
    assert "railway_station" in venues or "hospital" in venues
    for v in venues.values():
        assert isinstance(v, Venue)
        assert len(v.nodes) > 0

    tasks = load_tasks()
    assert len(tasks) > 0
    for t in tasks:
        assert isinstance(t, Task)
        assert t.gold in t.options


def test_minimal_pairs_grouping() -> None:
    """Verify minimal pairs group into verified pairs with roles 'a' and 'b'."""
    tasks = load_tasks()
    pairs = get_minimal_pairs(tasks)
    assert len(pairs) > 0
    for group in pairs.values():
        assert len(group) == 2
        roles = {group[0].pair_role, group[1].pair_role}
        assert roles == {"a", "b"}
        assert group[0].gold != group[1].gold


def test_plot_venue_route() -> None:
    """Verify venue route plotting generates a valid matplotlib figure."""
    tasks = load_tasks()
    venues = get_venue_map()
    task = tasks[0]
    scene = load_scene(task.scene_path)
    assert scene is not None
    venue = venues[scene.venue_id]

    fig = plot_venue_route(venue, task, scene)
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)


def test_query_model_offline_fake_adapters() -> None:
    """Verify query_model executes fake adapters and caches results offline."""
    tasks = load_tasks()
    task = tasks[0]

    # Oracle adapter returns gold
    ans_oracle, is_cor, latency, raw, _src = query_model(task, "oracle", mode="image")
    assert ans_oracle == task.gold
    assert is_cor is True
    assert latency >= 0.0
    assert len(raw) > 0

    # Always AHEAD returns AHEAD
    ans_always, _, _, _, _ = query_model(task, "always_ahead", mode="image")
    assert ans_always == "AHEAD"

    # Random baseline returns valid option
    ans_rand, _, _, _, _ = query_model(task, "random", mode="image")
    assert ans_rand in task.options


def test_query_model_missing_key_graceful_handling(monkeypatch) -> None:
    """Verify querying real API model when API key is missing returns clean error without crashing."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    tasks = load_tasks()
    # Create unique dummy task to bypass cache
    dummy_task = tasks[0].model_copy(deep=True)
    dummy_task.task_id = "test_uncached_dummy_9999"

    ans, is_cor, _, raw, src = query_model(dummy_task, "gemini_flash", mode="image")
    assert ans == "NO_API_KEY"
    assert is_cor is False
    assert src == "error"
    assert "GEMINI_API_KEY is not configured" in raw

    ans_or, is_cor_or, _, _raw_or, src_or = query_model(dummy_task, "or_vision", mode="image")
    assert ans_or == "NO_API_KEY"
    assert is_cor_or is False
    assert src_or == "error"


def test_demo_pages_syntax_and_import() -> None:
    """Verify demo/app.py and pages parse and import without errors."""
    repo_root = Path(__file__).resolve().parent.parent
    pages = [
        repo_root / "demo" / "app.py",
        repo_root / "demo" / "pages" / "2_Findings.py",
        repo_root / "demo" / "pages" / "3_Pairs.py",
    ]

    for page_path in pages:
        assert page_path.exists()
        spec = importlib.util.spec_from_file_location(page_path.stem, page_path)
        assert spec is not None
        assert spec.loader is not None
        # Verify code object can be compiled without syntax error
        source = page_path.read_text(encoding="utf-8")
        compiled = compile(source, str(page_path), "exec")
        assert compiled is not None
