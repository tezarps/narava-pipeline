#!/usr/bin/env python3
"""Generate a sample thumbnail. Output to Desktop."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agents.assembly_agent import create_thumbnail

IMAGE = Path(__file__).parent / "images" / "greek" / "zeus" / "01.jpeg"
TITLE = "Serving Zeus on Mount Olympus for Sleep | Ancient Greece"
OUT = Path.home() / "Desktop" / "narava_thumbnail_sample.jpg"

print(f"Generating thumbnail from {IMAGE.name}...")
create_thumbnail(IMAGE, TITLE, OUT)
print(f"Done → {OUT}")
