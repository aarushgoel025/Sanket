"""Unit tests for headless renderer, geometry export, and metadata stripping.

Tests template rendering across all layouts, font loading, arrow angle fidelity,
occlusion detection, and byte-level determinism.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from sanket.generator.renderer import render_scene
from sanket.generator.scene_builder import build_scene, sample_knobs
from sanket.graph.venue import load_venue
from sanket.schema import Distractor, Geometry, Venue

STATION_PATH = Path("config/venues/railway_station.yaml")


@pytest.fixture
def station_venue() -> Venue:
    """Fixture providing Central Junction Station venue."""
    return load_venue(STATION_PATH)


@pytest.mark.parametrize("template_name", ["board_list", "board_grid", "board_gantry"])
def test_render_three_templates_with_hindi(station_venue: Venue, template_name: str) -> None:
    """Render 3 scenes (one per template) with Hindi text and assert geometry and output."""
    rng = np.random.default_rng(123)
    knobs = sample_knobs(rng, "DIRECT")
    knobs = knobs.model_copy(
        update={
            "template": template_name,
            "scripts": ["en", "hi"],
            "n_entries": 4,
        }
    )

    build = build_scene(station_venue, "DIRECT", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / f"{template_name}.png"
        geo = render_scene(build.scene, station_venue, out_png)

        assert isinstance(geo, Geometry)
        assert len(geo.elements) > 0
        assert out_png.exists()

        with Image.open(out_png) as img:
            assert img.size == (1280, 720)


def test_arrow_angle_fidelity(station_venue: Venue) -> None:
    """Verify geometry contains an arrow for each entry with matching angle within 1 degree."""
    rng = np.random.default_rng(456)
    knobs = sample_knobs(rng, "DIRECT")
    knobs = knobs.model_copy(update={"n_entries": 4, "template": "board_list"})
    build = build_scene(station_venue, "DIRECT", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "arrow_test.png"
        geo = render_scene(build.scene, station_venue, out_png)

        arrows = [e for e in geo.elements if e.role == "arrow"]
        assert len(arrows) >= len(build.scene.entries)

        for entry in build.scene.entries:
            matching_arrows = [a for a in arrows if a.dest_id == entry.dest_id]
            assert len(matching_arrows) >= 1
            arrow_geo = matching_arrows[0]
            assert arrow_geo.angle is not None
            # Allow for 0 == 360 wrap-around
            diff = abs(arrow_geo.angle - entry.arrow_angle) % 360
            assert diff <= 1.0 or diff >= 359.0


def test_deliberate_overlapping_distractor_occludes(station_venue: Venue) -> None:
    """A deliberately placed distractor over an arrow must produce occluded_ratio > 0."""
    rng = np.random.default_rng(789)
    knobs = sample_knobs(rng, "DIRECT")
    knobs = knobs.model_copy(update={"n_entries": 3, "clutter": 0, "template": "board_list"})
    build = build_scene(station_venue, "DIRECT", rng, knobs)

    # First render clean to locate first arrow's center
    with tempfile.TemporaryDirectory() as tmpdir:
        clean_png = Path(tmpdir) / "clean.png"
        clean_geo = render_scene(build.scene, station_venue, clean_png)

        arrow_elem = next(e for e in clean_geo.elements if e.role == "arrow")
        # Compute normalized position of arrow center
        ax, ay, aw, ah = arrow_elem.bbox
        center_x = (ax + aw / 2.0) / 1280.0
        center_y = (ay + ah / 2.0) / 720.0

        # Inject an overlapping distractor right on top of this arrow
        overlapping_distractor = Distractor(
            id="blocking_ad",
            kind="ad",
            content="SUPER DISCOUNT ADVERTISEMENT BLOCKING",
            position=(center_x, center_y),
        )
        occluded_scene = build.scene.model_copy(update={"distractors": [overlapping_distractor]})

        occluded_png = Path(tmpdir) / "occluded.png"
        occluded_geo = render_scene(occluded_scene, station_venue, occluded_png)

        # Target arrow in occluded scene must show occluded_ratio > 0
        target_arrow = next(
            e
            for e in occluded_geo.elements
            if e.role == "arrow" and e.dest_id == arrow_elem.dest_id
        )
        assert target_arrow.occluded_ratio > 0.0


def test_png_has_no_metadata(station_venue: Venue) -> None:
    """Assert output PNG has no EXIF or non-standard text metadata chunks."""
    rng = np.random.default_rng(999)
    knobs = sample_knobs(rng, "DIRECT")
    build = build_scene(station_venue, "DIRECT", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_png = Path(tmpdir) / "no_meta.png"
        render_scene(build.scene, station_venue, out_png)

        with Image.open(out_png) as img:
            # Pillow stores PNG text chunks in img.info
            # Ensure no exif or descriptive metadata
            assert "exif" not in img.info
            assert "Comment" not in img.info
            assert "Description" not in img.info
            assert "Author" not in img.info


def test_identical_scene_gives_identical_pixels(station_venue: Venue) -> None:
    """Verify same Scene specification renders identical pixel bytes."""
    rng = np.random.default_rng(42)
    knobs = sample_knobs(rng, "DIRECT")
    knobs = knobs.model_copy(update={"n_entries": 3, "clutter": 2})
    build = build_scene(station_venue, "DIRECT", rng, knobs)

    with tempfile.TemporaryDirectory() as tmpdir:
        png1 = Path(tmpdir) / "render1.png"
        png2 = Path(tmpdir) / "render2.png"

        render_scene(build.scene, station_venue, png1)
        render_scene(build.scene, station_venue, png2)

        bytes1 = png1.read_bytes()
        bytes2 = png2.read_bytes()
        assert bytes1 == bytes2
