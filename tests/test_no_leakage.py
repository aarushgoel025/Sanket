"""Unit tests verifying zero ground-truth, receipt, or filesystem leakage.

Core contract requirements:
1. Prompts built for models contain the question, the options and the image
   (or text description) only.
2. Prompts never include gold, scene_path, scene contents, receipts or file names.
3. Generated PNG files have all metadata stripped (no EXIF, tEXt, zTXt, iTXt chunks).
"""

import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from sanket.evaluate.prompts import build_prompt
from sanket.generator.augment import augment
from sanket.schema import (
    ANSWER_OPTIONS,
    BoardEntry,
    Distractor,
    Edge,
    Geometry,
    Knobs,
    Label,
    Node,
    Receipt,
    Scene,
    Task,
    Venue,
)


@pytest.fixture
def mock_venue() -> Venue:
    """Fixture providing a mock venue layout."""
    return Venue(
        id="station_test",
        name="Test Station",
        kind="railway",
        nodes=[
            Node(
                id="j1",
                kind="junction",
                label=Label(en="Main Concourse", hi="मुख्य हॉल"),
            ),
            Node(
                id="dest_secret_a",
                kind="destination",
                label=Label(en="Platform 1", hi="प्लेटफॉर्म 1"),
            ),
            Node(
                id="dest_secret_b",
                kind="destination",
                label=Label(en="Ticket Counter", hi="टिकट काउंटर"),
            ),
        ],
        edges=[
            Edge(
                a="j1",
                b="dest_secret_a",
                bearing_ab=0,
                length=20.0,
            ),
            Edge(
                a="j1",
                b="dest_secret_b",
                bearing_ab=90,
                length=30.0,
            ),
        ],
    )


@pytest.fixture
def mock_scene() -> Scene:
    """Fixture providing a mock scene."""
    knobs = Knobs(
        n_entries=2,
        scripts=["latin", "devanagari"],
        perspective_deg=0.0,
        blur=0.0,
        noise=0.0,
        lighting=0.0,
        clutter=0,
        occlusion=0.0,
        jpeg_quality=95,
        template="board_list.html.j2",
    )
    return Scene(
        scene_id="secret_scene_id_9999",
        venue_id="station_test",
        junction_id="j1",
        heading=0,
        entries=[
            BoardEntry(
                dest_id="dest_secret_a",
                label=Label(en="Platform 1", hi="प्लेटफॉर्म 1"),
                arrow_angle=0,
                source="permanent",
                status="open",
            ),
            BoardEntry(
                dest_id="dest_secret_b",
                label=Label(en="Ticket Counter", hi="टिकट काउंटर"),
                arrow_angle=90,
                source="permanent",
                status="open",
            ),
        ],
        distractors=[Distractor(kind="text", content="Station Master")],
        knobs=knobs,
        closed_edges=[],
    )


@pytest.fixture
def mock_task() -> Task:
    """Fixture providing a task with unique identifiable secret markers."""
    receipt = Receipt(
        solver_answer="RIGHT",
        independent_answer="RIGHT",
        agree=True,
        fidelity_ok=True,
        visibility_ok=True,
        evidence_visible_ratio=0.99,
    )
    return Task(
        task_id="task_super_secret_id_42",
        schema_version="1.0.0",
        generator_version="1.0.0",
        seed=424242,
        qtype="DIRECT",
        question="Which direction should a passenger turn to reach Platform 1?",
        options=list(ANSWER_OPTIONS),
        gold="RIGHT",
        image_path="/data/full_dataset/images/task_secret_image_42.png",
        scene_path="/data/full_dataset/scenes/task_secret_scene_42.json",
        target_dest_id="dest_secret_a",
        turn_cw=None,
        pair_id="secret_pair_id_77",
        pair_role="a",
        receipt=receipt,
    )


def test_image_prompt_no_leakage(mock_task: Task) -> None:
    """Verify that image-mode prompt contains zero metadata or ground truth."""
    prompt = build_prompt(mock_task, mode="image", version="v1")

    # 1. Standard question and options must be present
    assert mock_task.question in prompt
    for opt in ANSWER_OPTIONS:
        assert opt in prompt

    # 2. Secret file paths or basenames must NEVER be present
    assert mock_task.image_path not in prompt
    assert Path(mock_task.image_path).name not in prompt
    assert mock_task.scene_path not in prompt
    assert Path(mock_task.scene_path).name not in prompt

    # 3. Task metadata must NEVER be present
    assert mock_task.task_id not in prompt
    assert str(mock_task.seed) not in prompt
    assert mock_task.qtype not in prompt
    assert mock_task.target_dest_id not in prompt
    assert "secret_pair_id_77" not in prompt

    # 4. Receipt data must NEVER be present
    assert "fidelity_ok" not in prompt
    assert "visibility_ok" not in prompt
    assert "evidence_visible_ratio" not in prompt
    assert "0.99" not in prompt
    assert "solver_answer" not in prompt
    assert "independent_answer" not in prompt

    # 5. Must NOT have any line asserting or revealing the answer
    lines = prompt.strip().split("\n")
    # Last line should be the formatting instruction
    assert lines[-1] == "Reply with exactly one line: ANSWER: <OPTION>"
    assert not any(line.startswith("ANSWER:") for line in lines[:-1])


def test_text_prompt_no_leakage(mock_task: Task, mock_scene: Scene, mock_venue: Venue) -> None:
    """Verify that text-mode prompt describes board contents without leaking gold or metadata."""
    prompt = build_prompt(mock_task, mode="text", version="v1", scene=mock_scene, venue=mock_venue)

    # 1. Question and options must be present
    assert mock_task.question in prompt
    for opt in ANSWER_OPTIONS:
        assert opt in prompt

    # 2. File paths and IDs must NEVER leak
    assert mock_task.image_path not in prompt
    assert Path(mock_task.image_path).name not in prompt
    assert mock_task.scene_path not in prompt
    assert Path(mock_task.scene_path).name not in prompt
    assert mock_task.task_id not in prompt
    assert mock_scene.scene_id not in prompt

    # 3. Receipt data must NEVER leak
    assert "fidelity" not in prompt
    assert "visibility" not in prompt
    assert "evidence" not in prompt
    assert "solver" not in prompt
    assert "independent" not in prompt
    assert "receipt" not in prompt

    # 4. Prompt instruction format
    assert prompt.endswith("Reply with exactly one line: ANSWER: <OPTION>")


def _get_png_chunk_types(png_bytes: bytes) -> list[str]:
    """Parse PNG byte stream and extract all chunk type identifiers."""
    # PNG signature is 8 bytes
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    chunk_types: list[str] = []
    while pos < len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        pos += 4
        chunk_type = png_bytes[pos : pos + 4].decode("latin-1")
        chunk_types.append(chunk_type)
        pos += 4
        pos += length  # skip chunk data
        pos += 4  # skip CRC
    return chunk_types


def test_augmented_png_metadata_stripped(tmp_path: Path) -> None:
    """Verify that saved PNG files have all metadata stripped (contract #7)."""
    # 1. Create a raw image with intentional metadata chunks
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Author", "Test Author")
    png_info.add_text("Comment", "Confidential Gold Answer RIGHT")
    png_info.add_text("Description", "Leakage test image")

    dirty_png = tmp_path / "dirty.png"
    img.save(dirty_png, format="PNG", pnginfo=png_info)

    # Verify that dirty_png indeed contains text metadata
    dirty_bytes = dirty_png.read_bytes()
    dirty_chunks = _get_png_chunk_types(dirty_bytes)
    assert any(c in ("tEXt", "zTXt", "iTXt") for c in dirty_chunks)

    # 2. Run through augment()
    clean_png = tmp_path / "clean.png"
    geo = Geometry(elements=[])
    knobs = Knobs(
        n_entries=3,
        scripts=["latin"],
        perspective_deg=0.0,
        blur=0.0,
        noise=0.0,
        lighting=0.0,
        clutter=0,
        occlusion=0.0,
        jpeg_quality=95,
        template="board_list.html.j2",
    )
    rng = np.random.default_rng(12345)

    augment(dirty_png, geo, knobs, rng, clean_png)

    # 3. Verify clean_png metadata is completely stripped
    clean_bytes = clean_png.read_bytes()
    clean_chunks = _get_png_chunk_types(clean_bytes)

    # Disallowed metadata chunk types
    disallowed_chunks = {"tEXt", "zTXt", "iTXt", "eXIf", "tIME"}
    found_disallowed = set(clean_chunks).intersection(disallowed_chunks)
    assert not found_disallowed, f"PNG contains disallowed metadata chunks: {found_disallowed}"

    # Also verify PIL image info is empty
    with Image.open(clean_png) as clean_im:
        assert not clean_im.info.get("Author")
        assert not clean_im.info.get("Comment")
        assert not clean_im.info.get("Description")
        assert not clean_im.info.get("exif")


def test_committed_sample_task_images_metadata_stripped() -> None:
    """Verify that all committed sample task PNGs have zero metadata chunks (contract #7)."""
    sample_images_dir = Path("data/sample_tasks/images")
    if not sample_images_dir.exists():
        pytest.skip("data/sample_tasks/images directory not found")

    png_files = list(sample_images_dir.glob("*.png"))
    assert len(png_files) > 0, "Expected at least 1 sample task PNG"

    disallowed_chunks = {"tEXt", "zTXt", "iTXt", "eXIf", "tIME"}

    for png_path in png_files:
        png_bytes = png_path.read_bytes()
        chunks = _get_png_chunk_types(png_bytes)
        leaked = set(chunks).intersection(disallowed_chunks)
        assert not leaked, f"{png_path} contains leaked metadata chunks: {leaked}"


def test_no_prepopulated_answer_in_prompts(mock_task: Task) -> None:
    """Ensure no prompt includes ANSWER: <GOLD> prior to model response."""
    import re

    prompt = build_prompt(mock_task, mode="image")
    # Must only match the instructional directive line, not an actual answer
    matches = re.findall(r"ANSWER:\s*(.+)", prompt)
    assert matches == ["<OPTION>"], f"Unexpected answer match in prompt: {matches}"
