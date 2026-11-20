"""EXIF metadata removal utility for real signboard photographs.

Ensures strict compliance with project rules (docs/rules.md section 4, docs/design.md section 7):
- All public signage photos must have EXIF metadata completely stripped.
- Re-saves pixel-identical image data with clean headers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def has_exif(image_path: Path | str) -> bool:
    """Check whether an image contains EXIF metadata.

    Args:
        image_path: Path to the image file.

    Returns:
        True if EXIF metadata is present, False otherwise.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found at {path}")

    with Image.open(path) as img:
        # Check standard Pillow getexif()
        exif = img.getexif()
        if exif is not None and len(exif) > 0:
            return True
        # Check img.info dictionary for raw exif bytes
        if "exif" in img.info and len(img.info["exif"]) > 0:
            return True
    return False


def strip_exif(image_path: Path | str) -> bool:
    """Strip EXIF metadata from a single image in-place.

    Args:
        image_path: Path to the image file.

    Returns:
        True if EXIF was detected and stripped, False if already clean.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found at {path}")

    with Image.open(path) as img:
        had_exif = (img.getexif() is not None and len(img.getexif()) > 0) or (
            "exif" in img.info and len(img.info["exif"]) > 0
        )
        img_format = img.format or "JPEG"
        img_mode = img.mode

        # Create clean canvas and copy pixel data
        clean = Image.new(img_mode, img.size)
        clean.paste(img)

        # Save back to file without metadata
        save_kwargs: dict[str, Any] = {}
        if img_format.upper() in ("JPEG", "JPG"):
            save_kwargs["quality"] = 95
        elif img_format.upper() == "PNG":
            save_kwargs["optimize"] = True

        clean.save(path, format=img_format, **save_kwargs)

    return had_exif


def strip_exif_directory(
    dir_path: Path | str = "data/real_photos/images",
) -> dict[str, int]:
    """Scan directory and remove EXIF from every image file found.

    Args:
        dir_path: Path to folder containing photos.

    Returns:
        Dictionary with 'scanned', 'stripped', and 'already_clean' counts.
    """
    folder = Path(dir_path)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)

    scanned = 0
    stripped = 0
    clean = 0

    image_files = sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    for img_file in image_files:
        scanned += 1
        if has_exif(img_file):
            strip_exif(img_file)
            stripped += 1
            print(f"Stripped EXIF: {img_file}")
        else:
            clean += 1

    return {"scanned": scanned, "stripped": stripped, "already_clean": clean}


def main() -> int:
    """CLI entrypoint for strip_exif."""
    parser = argparse.ArgumentParser(
        description="Strip EXIF metadata from real signboard photographs."
    )
    parser.add_argument(
        "--dir",
        "-d",
        type=Path,
        default=Path("data/real_photos/images"),
        help="Directory containing images to process (default: data/real_photos/images)",
    )
    args = parser.parse_args()

    target_dir = args.dir
    print(f"Processing images in: {target_dir}")
    stats = strip_exif_directory(target_dir)
    print(
        f"Summary: {stats['scanned']} scanned, "
        f"{stats['stripped']} stripped, {stats['already_clean']} already clean."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
