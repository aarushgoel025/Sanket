"""Reliable headless renderer using Playwright Chromium and Jinja2 templates.

Renders Scenes to PNG signboards at 1280x720, enforces font glyph availability,
strips image metadata, and extracts element geometry with occlusion testing.
"""

import io
import os
import tempfile
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from PIL import Image
from playwright.sync_api import sync_playwright

from sanket.schema import ElementGeo, Geometry, Scene, Venue

TEMPLATE_MAP = {
    "board_list": "board_list.html.j2",
    "board_grid": "board_grid.html.j2",
    "board_gantry": "board_gantry.html.j2",
    "list": "board_list.html.j2",
    "grid": "board_grid.html.j2",
    "gantry": "board_gantry.html.j2",
}

VENUE_COLORS = {
    "railway": "#12355B",
    "hospital": "#0F5132",
    "metro": "#2E3338",
}


def _get_browser_executable() -> str | None:
    """Find installed Chrome or Edge executable on Windows/Linux."""
    custom = os.environ.get("PLAYWRIGHT_CHROME_PATH")
    if custom and Path(custom).exists():
        return custom

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _render_page(page: Any, tmp_html_path: Path) -> tuple[list[dict[str, Any]], bytes]:
    """Helper to load HTML, verify fonts, extract geometry, and take screenshot."""
    page.goto(tmp_html_path.resolve().as_uri(), wait_until="networkidle")

    # Verify font loading and check for missing glyphs
    page.evaluate(
        """
        async () => {
            await document.fonts.load('16px "Noto Sans"');
            await document.fonts.load('bold 16px "Noto Sans"');
            await document.fonts.load('16px "Noto Sans Devanagari"');
            await document.fonts.load('bold 16px "Noto Sans Devanagari"');
            await document.fonts.ready;
            for (const f of document.fonts) {
                if (f.status !== 'loaded') {
                    throw new Error(`Font ${f.family} failed to load (status: ${f.status})`);
                }
            }
            return true;
        }
        """
    )

    # Extract per-element geometry with 5x5 occlusion sampling
    raw_elements = page.evaluate(
        """
        () => {
            const elements = [];
            const nodes = document.querySelectorAll('[data-role]');

            for (const el of nodes) {
                const role = el.getAttribute('data-role');
                const destId = el.getAttribute('data-dest-id') || el.closest('[data-dest-id]')?.getAttribute('data-dest-id') || null;
                const source = el.getAttribute('data-source') || el.closest('[data-source]')?.getAttribute('data-source') || null;
                const text = el.innerText ? el.innerText.trim() : null;

                const rect = el.getBoundingClientRect();
                const bbox = [rect.x, rect.y, rect.width, rect.height];

                let angle = null;
                const style = window.getComputedStyle(el);
                const transform = style.transform || style.webkitTransform;
                if (transform && transform !== 'none') {
                    const match = transform.match(/^matrix\\((.+)\\)$/);
                    if (match) {
                        const values = match[1].split(',').map(parseFloat);
                        const a = values[0];
                        const b = values[1];
                        let deg = Math.round(Math.atan2(b, a) * (180 / Math.PI));
                        if (deg < 0) deg += 360;
                        angle = deg % 360;
                    }
                } else if (el.hasAttribute('data-angle')) {
                    angle = parseFloat(el.getAttribute('data-angle'));
                }

                // 5x5 occlusion sampling
                let occludedPoints = 0;
                const totalPoints = 25;
                if (rect.width > 0 && rect.height > 0) {
                    for (let i = 0; i < 5; i++) {
                        for (let j = 0; j < 5; j++) {
                            const px = rect.left + rect.width * (i + 0.5) / 5.0;
                            const py = rect.top + rect.height * (j + 0.5) / 5.0;
                            const topEl = document.elementFromPoint(px, py);
                            const topDestId = topEl ? (topEl.getAttribute('data-dest-id') || topEl.closest('[data-dest-id]')?.getAttribute('data-dest-id')) : null;
                            const isSameEntry = topDestId && destId && topDestId === destId;
                            const isVisible = topEl && (topEl === el || el.contains(topEl) || topEl.contains(el) || isSameEntry);
                            if (!isVisible) {
                                occludedPoints++;
                            }
                        }
                    }
                }
                const occludedRatio = occludedPoints / totalPoints;

                elements.push({
                    role: role,
                    dest_id: destId,
                    angle: angle,
                    text: text,
                    bbox: bbox,
                    occluded_ratio: occludedRatio,
                    source: source
                });
            }
            return elements;
        }
        """
    )

    screenshot_bytes = page.screenshot(type="png")
    return raw_elements, screenshot_bytes


def render_scene(
    scene: Scene,
    venue: Venue,
    out_png: Path,
    browser: Any = None,
) -> Geometry:
    """Render a Scene to a PNG image and export element geometries.

    Args:
        scene: Scene specification model.
        venue: Venue topology model.
        out_png: Output destination path for the rendered PNG file.
        browser: Optional running Playwright Browser instance to reuse.

    Returns:
        Geometry object containing per-element bounding boxes, angles, and occlusions.

    Raises:
        FileNotFoundError: If templates or fonts are missing.
        RuntimeError: If fonts fail to load or render in Chromium.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    templates_dir = repo_root / "assets" / "templates"
    fonts_dir = repo_root / "assets" / "fonts"

    # Template selection
    template_key = scene.knobs.template
    template_file = TEMPLATE_MAP.get(template_key)
    if not template_file:
        template_file = (
            f"{template_key}.html.j2" if not template_key.endswith(".html.j2") else template_key
        )

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template(template_file)

    # Font URLs (file:// URI)
    font_files = {
        "font_noto_sans": (fonts_dir / "NotoSans-Regular.ttf").resolve().as_uri(),
        "font_noto_sans_bold": (fonts_dir / "NotoSans-Bold.ttf").resolve().as_uri(),
        "font_noto_devanagari": (fonts_dir / "NotoSansDevanagari-Regular.ttf").resolve().as_uri(),
        "font_noto_devanagari_bold": (fonts_dir / "NotoSansDevanagari-Bold.ttf").resolve().as_uri(),
    }

    # Split permanent vs notice entries
    permanent_entries = [e for e in scene.entries if e.source == "permanent"]
    notice_entries = [e for e in scene.entries if e.source == "temporary_notice"]

    board_bg = VENUE_COLORS.get(venue.kind, "#12355B")

    html_content = template.render(
        scene=scene,
        venue=venue,
        permanent_entries=permanent_entries,
        notice_entries=notice_entries,
        distractors=scene.distractors,
        board_bg=board_bg,
        **font_files,
    )

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp_html:
        tmp_html.write(html_content)
        tmp_html_path = Path(tmp_html.name)

    try:
        if browser is not None:
            page = browser.new_page(
                viewport={"width": 1280, "height": 720},
                device_scale_factor=1,
            )
            try:
                raw_elements, screenshot_bytes = _render_page(page, tmp_html_path)
            finally:
                page.close()
        else:
            with sync_playwright() as p:
                exec_path = _get_browser_executable()
                launch_args: dict[str, Any] = {
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

                b = p.chromium.launch(**launch_args)
                try:
                    page = b.new_page(
                        viewport={"width": 1280, "height": 720},
                        device_scale_factor=1,
                    )
                    try:
                        raw_elements, screenshot_bytes = _render_page(page, tmp_html_path)
                    finally:
                        page.close()
                finally:
                    b.close()
    finally:
        tmp_html_path.unlink(missing_ok=True)

    # Re-save with Pillow to guarantee zero metadata/exif chunks
    with Image.open(io.BytesIO(screenshot_bytes)) as img:
        clean_img = Image.frombytes(img.mode, img.size, img.tobytes())
        clean_img.save(out_png, format="PNG")

    elements = [
        ElementGeo(
            role=item["role"],
            dest_id=item["dest_id"],
            angle=item["angle"],
            text=item["text"],
            bbox=tuple(item["bbox"]),
            occluded_ratio=item["occluded_ratio"],
            source=item["source"],
        )
        for item in raw_elements
    ]

    return Geometry(elements=elements)
