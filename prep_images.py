#!/usr/bin/env python3
"""
Usage: python3 prep_images.py <category> <topic>

Examples:
  python3 prep_images.py greek zeus
  python3 prep_images.py greek hera
  python3 prep_images.py norse odin
  python3 prep_images.py egyptian ra

Takes the 10 most recently downloaded images from ~/Downloads,
renames them 01.jpeg - 10.jpeg, and moves to images/<category>/<topic>/
"""
import sys
import shutil
from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"
IMAGES_DIR = Path(__file__).parent / "images"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 prep_images.py <category> <topic>")
        print("Example: python3 prep_images.py greek zeus")
        sys.exit(1)

    category = sys.argv[1].lower()
    topic = sys.argv[2].lower()
    target = IMAGES_DIR / category / topic

    if not target.exists():
        print(f"Folder not found: {target}")
        print(f"Available topics: {[d.name for d in (IMAGES_DIR / category).iterdir() if d.is_dir()]}")
        sys.exit(1)

    # Get 10 most recent image files from Downloads
    all_images = [
        f for f in DOWNLOADS.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSIONS
    ]
    all_images.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    selected = all_images[:10]

    if len(selected) < 10:
        print(f"Warning: only {len(selected)} images found in Downloads (need 10)")
        if not selected:
            sys.exit(1)

    # Sort by modification time ascending (oldest first = scene order)
    selected.sort(key=lambda f: f.stat().st_mtime)

    print(f"\nMoving {len(selected)} images → {target}/\n")
    for i, src in enumerate(selected, 1):
        dst = target / f"{i:02d}.jpeg"
        shutil.move(str(src), str(dst))
        print(f"  {src.name}  →  {dst.name}")

    print(f"\n✓ Done — {len(selected)} images ready in images/{category}/{topic}/")


if __name__ == "__main__":
    main()
