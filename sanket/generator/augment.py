"""Deterministic visual augmentation pipeline for signage images.

Applies seeded transformations in order:
1. Stickers/occluders outside evidence regions
2. Lighting gradient and shadow
3. Perspective warp (with homography applied to geometry)
4. Gaussian blur
5. Sensor noise
6. JPEG compression
7. PNG saving with metadata stripping
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from sanket.schema import ElementGeo, Geometry, Knobs

EVIDENCE_ROLES = {"label", "arrow", "closed_mark", "notice"}

STICKER_PALETTES = [
    ((255, 235, 150), (220, 180, 80)),
    ((200, 240, 200), (140, 190, 140)),
    ((220, 220, 245), (150, 150, 200)),
    ((250, 210, 210), (200, 140, 140)),
    ((240, 240, 240), (180, 180, 180)),
]


def _boxes_overlap(
    box1: tuple[float, float, float, float],
    box2: tuple[float, float, float, float],
    margin: float = 4.0,
) -> bool:
    """Check if two axis-aligned bounding boxes overlap within a safety margin."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    return not (
        (x1 + w1 + margin) < x2
        or (x2 + w2 + margin) < x1
        or (y1 + h1 + margin) < y2
        or (y2 + h2 + margin) < y1
    )


def _place_occluders(
    img: np.ndarray,
    geometry: Geometry,
    occlusion: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, list[tuple[float, float, float, float]]]:
    """Place stickers/occluders on the image outside all evidence bounding boxes.

    Args:
        img: RGB numpy image array.
        geometry: Scene geometry containing element bounding boxes.
        occlusion: Target occlusion fraction (0.0 to 0.15 of image area).
        rng: Seeded random generator.

    Returns:
        Tuple of (modified image array, list of placed occluder bounding boxes).
    """
    if occlusion <= 0.001:
        return img, []

    evidence_boxes = [e.bbox for e in geometry.elements if e.role in EVIDENCE_ROLES]
    total_area = float(img.shape[1] * img.shape[0])
    target_area = occlusion * total_area

    num_stickers = int(rng.integers(1, 4))
    placed_boxes: list[tuple[float, float, float, float]] = []

    out_img = img.copy()

    for _ in range(num_stickers):
        sticker_area = target_area / num_stickers
        aspect_ratio = float(rng.uniform(0.6, 1.8))
        sw = float(np.sqrt(sticker_area * aspect_ratio))
        sh = float(sticker_area / sw)

        sw = min(sw, img.shape[1] * 0.4)
        sh = min(sh, img.shape[0] * 0.4)

        placed = False
        for _ in range(200):
            max_x = max(1.0, img.shape[1] - sw - 10.0)
            max_y = max(1.0, img.shape[0] - sh - 10.0)
            sx = float(rng.uniform(10.0, max_x))
            sy = float(rng.uniform(10.0, max_y))

            candidate_box = (sx, sy, sw, sh)
            if not any(_boxes_overlap(candidate_box, ebox, margin=6.0) for ebox in evidence_boxes):
                # Candidate does not intersect any evidence
                color_idx = int(rng.integers(0, len(STICKER_PALETTES)))
                fill_color, border_color = STICKER_PALETTES[color_idx]

                x1, y1 = int(sx), int(sy)
                x2, y2 = int(sx + sw), int(sy + sh)

                cv2.rectangle(out_img, (x1, y1), (x2, y2), fill_color, -1)
                cv2.rectangle(out_img, (x1, y1), (x2, y2), border_color, 2)

                placed_boxes.append(candidate_box)
                placed = True
                break

        if not placed and sw > 20 and sh > 20:
            # Fallback with smaller sticker if needed
            sw *= 0.6
            sh *= 0.6

    return out_img, placed_boxes


def _apply_lighting(
    img: np.ndarray,
    lighting: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply seeded lighting gradient and soft directional shadow."""
    if lighting <= 0.01:
        return img

    h, w, _ = img.shape
    angle = float(rng.uniform(0.0, 2.0 * np.pi))
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)

    y_grid, x_grid = np.ogrid[:h, :w]
    nx = (x_grid - (w / 2.0)) / (w / 2.0)
    ny = (y_grid - (h / 2.0)) / (h / 2.0)
    proj = nx * cos_a + ny * sin_a

    gradient = 1.0 + (lighting * 0.7 * proj)

    cx = float(rng.uniform(w * 0.25, w * 0.75))
    cy = float(rng.uniform(h * 0.25, h * 0.75))
    dist = np.sqrt(((x_grid - cx) / (w / 2.0)) ** 2 + ((y_grid - cy) / (h / 2.0)) ** 2)
    shadow = 1.0 - (lighting * 0.3) * np.clip(dist, 0.0, 1.5) / 1.5

    factor = (gradient * shadow)[:, :, np.newaxis]
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def _apply_perspective(
    img: np.ndarray,
    geometry: Geometry,
    perspective_deg: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, Geometry]:
    """Apply seeded perspective warp to image and transform element bounding boxes."""
    if perspective_deg <= 0.05:
        return img, geometry

    h, w, _ = img.shape
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)

    intensity = min(1.0, max(0.0, perspective_deg / 25.0))
    dx_max = 75.0 * intensity
    dy_max = 45.0 * intensity

    dx = rng.uniform(0.1, 1.0, size=4) * dx_max
    dy = rng.uniform(0.1, 1.0, size=4) * dy_max

    dst = np.array(
        [
            [dx[0], dy[0]],
            [w - dx[1], dy[1]],
            [w - dx[2], h - dy[2]],
            [dx[3], h - dy[3]],
        ],
        dtype=np.float32,
    )

    homography = cv2.getPerspectiveTransform(src, dst)
    warped_img = cv2.warpPerspective(img, homography, (w, h), borderMode=cv2.BORDER_REPLICATE)

    transformed_elements: list[ElementGeo] = []
    for elem in geometry.elements:
        ex, ey, ew, eh = elem.bbox
        pts = np.array(
            [[[ex, ey]], [[ex + ew, ey]], [[ex + ew, ey + eh]], [[ex, ey + eh]]],
            dtype=np.float32,
        )
        warped_pts = cv2.perspectiveTransform(pts, homography).reshape(-1, 2)

        min_x = float(np.clip(warped_pts[:, 0].min(), 0.0, w))
        max_x = float(np.clip(warped_pts[:, 0].max(), 0.0, w))
        min_y = float(np.clip(warped_pts[:, 1].min(), 0.0, h))
        max_y = float(np.clip(warped_pts[:, 1].max(), 0.0, h))

        transformed_elements.append(
            ElementGeo(
                role=elem.role,
                dest_id=elem.dest_id,
                angle=elem.angle,
                text=elem.text,
                bbox=(min_x, min_y, max_x - min_x, max_y - min_y),
                occluded_ratio=elem.occluded_ratio,
                source=elem.source,
            )
        )

    return warped_img, Geometry(elements=transformed_elements)


def _apply_blur(img: np.ndarray, blur: float) -> np.ndarray:
    """Apply seeded Gaussian blur."""
    if blur <= 0.05:
        return img
    sigma = float(blur)
    k = int(np.ceil(sigma * 3)) // 2 * 2 + 1
    k = max(3, min(k, 15))
    return cv2.GaussianBlur(img, (k, k), sigmaX=sigma, sigmaY=sigma)


def _apply_noise(img: np.ndarray, noise: float, rng: np.random.Generator) -> np.ndarray:
    """Apply seeded Gaussian sensor noise."""
    if noise <= 0.0005:
        return img
    sigma = float(noise * 255.0)
    noise_mat = rng.normal(0.0, sigma, img.shape)
    return np.clip(img.astype(np.float32) + noise_mat, 0, 255).astype(np.uint8)


def _apply_jpeg(img: np.ndarray, quality: int) -> np.ndarray:
    """Apply JPEG DCT compression artifacts deterministically."""
    quality = max(10, min(100, int(quality)))
    success, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        return img
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def augment(
    png_in: Path,
    geometry: Geometry,
    knobs: Knobs,
    rng: np.random.Generator,
    out_png: Path,
) -> Geometry:
    """Apply seeded visual augmentations and export transformed geometry.

    Pipeline execution order:
    1. Stickers / occluders (outside evidence regions)
    2. Lighting gradient and shadow
    3. Perspective warp (with homography applied to geometry)
    4. Gaussian blur
    5. Sensor noise
    6. JPEG compression
    7. Save PNG with metadata stripped

    Args:
        png_in: Path to input clean PNG image.
        geometry: Geometry specification of elements in the clean image.
        knobs: Augmentation and difficulty knobs.
        rng: Seeded numpy random generator.
        out_png: Path where augmented image will be written.

    Returns:
        Transformed Geometry model.
    """
    png_in = Path(png_in)
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(png_in) as im:
        img_rgb = np.array(im.convert("RGB"))

    # 1. Stickers / occluders
    img_occ, _ = _place_occluders(img_rgb, geometry, knobs.occlusion, rng)

    # 2. Lighting gradient and shadow
    img_lit = _apply_lighting(img_occ, knobs.lighting, rng)

    # 3. Perspective warp
    img_warped, trans_geo = _apply_perspective(img_lit, geometry, knobs.perspective_deg, rng)

    # 4. Blur
    img_blurred = _apply_blur(img_warped, knobs.blur)

    # 5. Noise
    img_noisy = _apply_noise(img_blurred, knobs.noise, rng)

    # 6. JPEG compression
    img_final = _apply_jpeg(img_noisy, knobs.jpeg_quality)

    # 7. Save PNG and strip metadata
    clean_pil = Image.frombytes(
        "RGB", (img_final.shape[1], img_final.shape[0]), img_final.tobytes()
    )
    clean_pil.save(out_png, format="PNG")

    return trans_geo
