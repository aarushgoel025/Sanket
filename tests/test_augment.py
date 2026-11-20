"""Unit tests for visual augmentation pipeline.

Tests non-intersecting occluders, perspective boundary invariants,
byte-level determinism, and image metadata stripping.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from sanket.generator.augment import (
    EVIDENCE_ROLES,
    _boxes_overlap,
    _place_occluders,
    augment,
)
from sanket.generator.scene_builder import sample_knobs
from sanket.graph.venue import load_venue
from sanket.schema import ElementGeo, Geometry, Knobs, Venue

STATION_PATH = Path("config/venues/railway_station.yaml")


@pytest.fixture
def station_venue() -> Venue:
    """Fixture providing Central Junction Station venue."""
    return load_venue(STATION_PATH)


@pytest.fixture
def sample_rendered_scene(station_venue: Venue, tmp_path: Path) -> tuple[Path, Geometry, Knobs]:
    """Fixture generating a rendered clean scene and its geometry."""
    rng = np.random.default_rng(101)
    knobs = sample_knobs(rng, "DIRECT")
    knobs = knobs.model_copy(update={"n_entries": 4, "template": "board_list"})

    clean_png = tmp_path / "clean_base.png"
    img = Image.new("RGB", (1280, 720), color=(18, 53, 91))
    img.save(clean_png, format="PNG")

    geo = Geometry(
        elements=[
            ElementGeo(role="arrow", bbox=(220.0, 160.0, 48.0, 48.0), angle=0.0),
            ElementGeo(role="label", bbox=(290.0, 160.0, 300.0, 48.0), text="Platform 1"),
            ElementGeo(role="arrow", bbox=(220.0, 240.0, 48.0, 48.0), angle=90.0),
            ElementGeo(role="label", bbox=(290.0, 240.0, 320.0, 48.0), text="Concourse"),
            ElementGeo(role="arrow", bbox=(220.0, 320.0, 48.0, 48.0), angle=180.0),
            ElementGeo(role="label", bbox=(290.0, 320.0, 280.0, 48.0), text="Exit"),
            ElementGeo(role="arrow", bbox=(220.0, 400.0, 48.0, 48.0), angle=270.0),
            ElementGeo(role="label", bbox=(290.0, 400.0, 250.0, 48.0), text="Restroom"),
        ]
    )
    return clean_png, geo, knobs


def test_occluders_never_intersect_evidence_100_trials() -> None:
    """Verify in 100 random trials that occluders never intersect evidence bounding boxes."""
    # Synthetic evidence boxes simulating arrows and labels in a signboard
    evidence_elements = [
        ElementGeo(role="arrow", bbox=(220.0, 160.0, 48.0, 48.0)),
        ElementGeo(role="label", bbox=(290.0, 160.0, 300.0, 48.0)),
        ElementGeo(role="arrow", bbox=(220.0, 240.0, 48.0, 48.0)),
        ElementGeo(role="label", bbox=(290.0, 240.0, 320.0, 48.0)),
        ElementGeo(role="closed_mark", bbox=(200.0, 320.0, 450.0, 50.0)),
        ElementGeo(role="notice", bbox=(800.0, 450.0, 300.0, 150.0)),
    ]
    test_geo = Geometry(elements=evidence_elements)
    dummy_img = np.zeros((720, 1280, 3), dtype=np.uint8)

    for seed in range(100):
        rng = np.random.default_rng(2000 + seed)
        _, placed_boxes = _place_occluders(
            img=dummy_img,
            geometry=test_geo,
            occlusion=0.15,
            rng=rng,
        )

        for occ_box in placed_boxes:
            for elem in test_geo.elements:
                if elem.role in EVIDENCE_ROLES:
                    assert not _boxes_overlap(occ_box, elem.bbox, margin=0.0), (
                        f"Seed {seed}: Occluder {occ_box} overlapped with evidence {elem.role} {elem.bbox}"
                    )


def test_perspective_25_deg_evidence_boxes_inside_image(
    sample_rendered_scene: tuple[Path, Geometry, Knobs],
) -> None:
    """With perspective 25 degrees, transformed evidence boxes must stay inside the image."""
    clean_png, geo, knobs = sample_rendered_scene
    knobs = knobs.model_copy(update={"perspective_deg": 25.0, "occlusion": 0.0})

    for seed in range(20):
        rng = np.random.default_rng(3000 + seed)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = Path(tmpdir) / f"warped_{seed}.png"
            trans_geo = augment(clean_png, geo, knobs, rng, out_png)

            evidence_items = [e for e in trans_geo.elements if e.role in EVIDENCE_ROLES]
            assert len(evidence_items) > 0

            for elem in evidence_items:
                x, y, w, h = elem.bbox
                assert x >= 0.0, f"Seed {seed}: x < 0 ({x})"
                assert y >= 0.0, f"Seed {seed}: y < 0 ({y})"
                assert (x + w) <= 1280.0, f"Seed {seed}: x + w > 1280 ({x + w})"
                assert (y + h) <= 720.0, f"Seed {seed}: y + h > 720 ({y + h})"


def test_augment_determinism(sample_rendered_scene: tuple[Path, Geometry, Knobs]) -> None:
    """Verify that identical inputs and seed give identical output pixels and geometry."""
    clean_png, geo, knobs = sample_rendered_scene
    test_knobs = knobs.model_copy(
        update={
            "perspective_deg": 15.0,
            "lighting": 0.3,
            "blur": 1.2,
            "noise": 0.03,
            "jpeg_quality": 75,
            "occlusion": 0.08,
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out1 = Path(tmpdir) / "out1.png"
        out2 = Path(tmpdir) / "out2.png"

        rng1 = np.random.default_rng(9999)
        rng2 = np.random.default_rng(9999)

        geo1 = augment(clean_png, geo, test_knobs, rng1, out1)
        geo2 = augment(clean_png, geo, test_knobs, rng2, out2)

        # Byte-for-byte identical output
        assert out1.read_bytes() == out2.read_bytes()

        # Geometry identical
        assert [e.model_dump() for e in geo1.elements] == [e.model_dump() for e in geo2.elements]


def test_output_png_has_no_metadata(sample_rendered_scene: tuple[Path, Geometry, Knobs]) -> None:
    """Assert output PNG from augment pipeline contains no metadata or exif chunks."""
    clean_png, geo, knobs = sample_rendered_scene

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "clean_meta.png"
        rng = np.random.default_rng(42)
        augment(clean_png, geo, knobs, rng, out_png)

        with Image.open(out_png) as img:
            assert "exif" not in img.info
            assert "Comment" not in img.info
            assert "Description" not in img.info
            assert "Author" not in img.info


def test_full_pipeline_all_augmentations(
    sample_rendered_scene: tuple[Path, Geometry, Knobs],
) -> None:
    """Verify execution with all knobs at maximum difficulty."""
    clean_png, geo, _ = sample_rendered_scene
    max_knobs = Knobs(
        n_entries=4,
        scripts=["en", "hi"],
        perspective_deg=25.0,
        blur=2.5,
        noise=0.06,
        lighting=0.4,
        clutter=6,
        occlusion=0.15,
        jpeg_quality=60,
        template="board_list",
    )

    rng = np.random.default_rng(5555)
    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "max_augmented.png"
        trans_geo = augment(clean_png, geo, max_knobs, rng, out_png)

        assert out_png.exists()
        with Image.open(out_png) as img:
            assert img.size == (1280, 720)
        assert len(trans_geo.elements) == len(geo.elements)
