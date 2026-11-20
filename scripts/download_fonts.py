"""Download Noto Sans and Noto Sans Devanagari open-license TTF fonts via fast CDN."""

from pathlib import Path

import httpx

FONTS = {
    "NotoSans-Regular.ttf": "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
    "NotoSans-Bold.ttf": "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    "NotoSansDevanagari-Regular.ttf": "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf",
    "NotoSansDevanagari-Bold.ttf": "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf",
}

OUT_DIR = Path("assets/fonts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with httpx.Client(follow_redirects=True, timeout=30.0) as client:
    for name, url in FONTS.items():
        dest = OUT_DIR / name
        if not dest.exists() or dest.stat().st_size == 0:
            print(f"Downloading {name} from {url}...")
            resp = client.get(url)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                f.write(resp.content)
            print(f"Saved {name} ({dest.stat().st_size} bytes)")
        else:
            print(f"Already exists: {name} ({dest.stat().st_size} bytes)")
