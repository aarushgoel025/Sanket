"""Unit and integration tests for real-image evaluation set.

Tests:
1. EXIF stripping utility (scripts/strip_exif.py).
2. Real tasks integrity checker (scripts/check_real_tasks.py).
3. Evaluation runner on real dataset (sanket/evaluate/runner.py with task_set="real").
4. Figure F5 generation with 95% Wilson intervals and sample size n.
5. CLI command `sanket eval --set real`.
"""

from pathlib import Path

import pandas as pd
import pytest
from PIL import Image
from typer.testing import CliRunner

from sanket.analysis.heatmaps import generate_f5_synthetic_vs_real
from sanket.analysis.metrics import compute_synthetic_vs_real_metrics
from sanket.cli import app
from sanket.evaluate.adapters.fake import AlwaysAdapter, OracleAdapter
from sanket.evaluate.runner import run_evaluation
from sanket.schema import ANSWER_OPTIONS
from scripts.check_real_tasks import check_real_task_entry, check_real_tasks_file
from scripts.strip_exif import has_exif, strip_exif, strip_exif_directory


@pytest.fixture
def temp_image_with_exif(tmp_path: Path) -> Path:
    """Create a temporary JPEG with synthetic EXIF metadata."""
    img_path = tmp_path / "test_with_exif.jpg"
    img = Image.new("RGB", (64, 64), color="blue")
    exif = img.getexif()
    exif[0x010F] = "TestCameraManufacturer"  # Make
    exif[0x0110] = "TestModel123"  # Model
    img.save(img_path, "JPEG", exif=exif)
    return img_path


def test_has_exif_and_strip_exif(temp_image_with_exif: Path):
    """Verify has_exif correctly detects metadata and strip_exif removes it."""
    assert has_exif(temp_image_with_exif) is True

    stripped = strip_exif(temp_image_with_exif)
    assert stripped is True
    assert has_exif(temp_image_with_exif) is False

    # Second run is idempotent and returns False
    stripped_again = strip_exif(temp_image_with_exif)
    assert stripped_again is False
    assert has_exif(temp_image_with_exif) is False


def test_strip_exif_directory(tmp_path: Path):
    """Verify batch EXIF stripping across directory."""
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"

    im = Image.new("RGB", (32, 32), color="red")
    exif = im.getexif()
    exif[0x010F] = "Camera1"
    im.save(img1, "JPEG", exif=exif)

    # Clean image without exif
    clean_im = Image.new("RGB", (32, 32), color="green")
    clean_im.save(img2, "JPEG")

    stats = strip_exif_directory(tmp_path)
    assert stats["scanned"] == 2
    assert stats["stripped"] == 1
    assert stats["already_clean"] == 1

    assert has_exif(img1) is False
    assert has_exif(img2) is False


def test_sample_real_tasks_integrity():
    """Verify the 5 committed sample real tasks pass check_real_tasks_file cleanly."""
    real_tasks_file = Path("data/real_photos/real_tasks.jsonl")
    assert real_tasks_file.exists(), "data/real_photos/real_tasks.jsonl must exist"

    tasks = check_real_tasks_file(real_tasks_file)
    assert len(tasks) == 5

    for t in tasks:
        assert t.task_id.startswith("R")
        assert t.task_set == "real"
        assert t.qtype == "REAL"
        assert t.gold in ANSWER_OPTIONS
        assert t.options == ANSWER_OPTIONS
        assert Path(t.image_path).exists()
        assert not has_exif(t.image_path)
        assert t.notes != ""


def test_check_real_task_entry_failures(tmp_path: Path):
    """Verify check_real_task_entry rejects invalid tasks with descriptive errors."""
    valid_img = tmp_path / "valid.jpg"
    Image.new("RGB", (32, 32), color="gray").save(valid_img, "JPEG")

    base = {
        "task_id": "R999",
        "image_path": str(valid_img),
        "question": "Which way?",
        "options": ANSWER_OPTIONS,
        "gold": "LEFT",
        "notes": "hand-labelled by Tester",
    }

    # Options not a list
    with pytest.raises(TypeError, match="must be a list"):
        check_real_task_entry({**base, "options": "not_a_list"}, 1, tmp_path)

    # Missing task_id
    with pytest.raises(ValueError, match="task_id"):
        check_real_task_entry({**base, "task_id": ""}, 1, tmp_path)

    # Invalid gold
    with pytest.raises(ValueError, match="not a valid option"):
        check_real_task_entry({**base, "gold": "INVALID_DIR"}, 1, tmp_path)

    # Missing question
    with pytest.raises(ValueError, match="question"):
        check_real_task_entry({**base, "question": ""}, 1, tmp_path)

    # Missing notes
    with pytest.raises(ValueError, match="notes"):
        check_real_task_entry({**base, "notes": ""}, 1, tmp_path)

    # Non-existent image
    with pytest.raises(FileNotFoundError, match="Image file not found"):
        check_real_task_entry({**base, "image_path": "non_existent.jpg"}, 1, tmp_path)

    # Image with EXIF
    exif_img = tmp_path / "has_exif.jpg"
    im = Image.new("RGB", (32, 32), color="red")
    ex = im.getexif()
    ex[0x010F] = "Test"
    im.save(exif_img, "JPEG", exif=ex)
    with pytest.raises(ValueError, match="contains EXIF metadata"):
        check_real_task_entry({**base, "image_path": str(exif_img)}, 1, tmp_path)


def test_evaluate_runner_real_set(tmp_path: Path):
    """Verify run_evaluation on real dataset runs in image-mode only with fake adapter."""
    real_tasks_file = Path("data/real_photos/real_tasks.jsonl")
    results_file = tmp_path / "test_real_results.jsonl"

    oracle = OracleAdapter()
    always = AlwaysAdapter(option="AHEAD")

    # Run evaluation requesting both image and text modes; runner must restrict to image
    results, _metrics = run_evaluation(
        tasks=real_tasks_file,
        models=[oracle, always],
        modes=["image", "text"],
        results_file=results_file,
        task_set="real",
    )

    assert len(results) == 10  # 5 tasks x 2 models x 1 mode (image only)
    assert all(r.mode == "image" for r in results)
    assert all(r.task_set == "real" for r in results)

    # Oracle must have 100% accuracy on real tasks
    oracle_res = [r for r in results if r.model_id == "oracle"]
    assert len(oracle_res) == 5
    assert all(r.correct for r in oracle_res)

    # AlwaysAdapter('AHEAD') should match exactly tasks where gold is AHEAD (R002)
    always_res = [r for r in results if r.model_id == "always_ahead"]
    assert len(always_res) == 5
    ahead_tasks = [r for r in always_res if r.correct]
    assert len(ahead_tasks) == 1
    assert ahead_tasks[0].task_id == "R002"


def test_compute_synthetic_vs_real_metrics_and_f5(tmp_path: Path):
    """Verify compute_synthetic_vs_real_metrics and generate_f5_synthetic_vs_real."""
    # Synthetic records
    records = [
        # Model A: 4 synth (3 correct), 2 real (2 correct)
        {
            "task_id": "task_001",
            "model_id": "model_a",
            "mode": "image",
            "correct": True,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_002",
            "model_id": "model_a",
            "mode": "image",
            "correct": True,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_003",
            "model_id": "model_a",
            "mode": "image",
            "correct": True,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_004",
            "model_id": "model_a",
            "mode": "image",
            "correct": False,
            "task_set": "synthetic",
        },
        {
            "task_id": "R001",
            "model_id": "model_a",
            "mode": "image",
            "correct": True,
            "task_set": "real",
        },
        {
            "task_id": "R002",
            "model_id": "model_a",
            "mode": "image",
            "correct": True,
            "task_set": "real",
        },
        # Model B: 4 synth (2 correct), 2 real (1 correct)
        {
            "task_id": "task_001",
            "model_id": "model_b",
            "mode": "image",
            "correct": True,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_002",
            "model_id": "model_b",
            "mode": "image",
            "correct": False,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_003",
            "model_id": "model_b",
            "mode": "image",
            "correct": True,
            "task_set": "synthetic",
        },
        {
            "task_id": "task_004",
            "model_id": "model_b",
            "mode": "image",
            "correct": False,
            "task_set": "synthetic",
        },
        {
            "task_id": "R001",
            "model_id": "model_b",
            "mode": "image",
            "correct": True,
            "task_set": "real",
        },
        {
            "task_id": "R002",
            "model_id": "model_b",
            "mode": "image",
            "correct": False,
            "task_set": "real",
        },
    ]
    df = pd.DataFrame(records)

    metrics_df = compute_synthetic_vs_real_metrics(df)
    assert len(metrics_df) == 2

    row_a = metrics_df[metrics_df["model_id"] == "model_a"].iloc[0]
    assert row_a["synth_total"] == 4
    assert row_a["synth_correct"] == 3
    assert row_a["synth_accuracy"] == 0.75
    assert row_a["real_total"] == 2
    assert row_a["real_correct"] == 2
    assert row_a["real_accuracy"] == 1.0
    assert row_a["accuracy_gap"] == 0.25

    # Generate F5 figure
    f5_out = tmp_path / "F5_test.png"
    meta = generate_f5_synthetic_vs_real(df, f5_out)
    assert f5_out.exists()
    assert f5_out.stat().st_size > 1000
    assert meta["fig_id"] == "F5"
    assert "real signboards" in meta["takeaway"].lower()


def test_cli_eval_set_real(tmp_path: Path):
    """Test CLI sanket eval --set real with fake models produces F5."""
    runner = CliRunner()
    out_results = tmp_path / "cli_results.jsonl"

    result = runner.invoke(
        app,
        [
            "eval",
            "--set",
            "real",
            "--out",
            str(out_results),
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0, f"CLI exited with error: {result.stdout}"
    assert "Running evaluation on" in result.stdout
    assert "set: real" in result.stdout
    assert "Figure F5 produced" in result.stdout
    assert Path("reports/figures/F5_synthetic_vs_real.png").exists()
