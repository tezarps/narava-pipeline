#!/usr/bin/env python3
"""One-off generator for the 8 contextual ambience loops used to make background
audio scene-relevant instead of one static per-category music track (see
assets/ambience/ — consumed by assembly_agent.py's per-segment ambience map).
Uses ElevenLabs' Sound Generation endpoint, billed ~40 credits/sec from the same
credit pool as narration TTS."""
import pathlib
import requests
from config import ELEVENLABS_API_KEY

SOUND_URL = "https://api.elevenlabs.io/v1/sound-generation"
OUT_DIR = pathlib.Path(__file__).parent / "assets" / "ambience"

TRACKS = {
    "rain": "Steady, gentle rain falling continuously, soft pattering, calm ambient loop, no thunder",
    "ocean_waves": "Calm ocean waves rolling onto a shore at night, steady rhythmic loop, peaceful, no wind gusts",
    "forest_birds": "Quiet forest at dawn, distant gentle birdsong, soft rustling leaves, peaceful ambient loop",
    "desert_wind": "Soft steady desert wind over sand and stone, low continuous whoosh, no gusts or sand storm",
    "fire_crackle": "Gentle wood fire crackling steadily in a hearth, soft warm continuous loop, no popping sparks",
    "night_crickets": "Quiet night ambience with distant steady crickets, very calm, soft, peaceful loop",
    "temple_hall": "Vast quiet stone hall with soft echo, faint distant incense-bell tone, very calm ambient loop",
    "river_stream": "Small calm river stream flowing steadily over stones, soft continuous water sound, peaceful loop",
}

DURATION_SECONDS = 30


def generate_sound(prompt, out_path):
    resp = requests.post(
        SOUND_URL,
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={
            "text": prompt,
            "duration_seconds": DURATION_SECONDS,
            "prompt_influence": 0.3,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code}: {resp.text[:400]}")
    out_path.write_bytes(resp.content)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, prompt in TRACKS.items():
        out_path = OUT_DIR / f"{name}.mp3"
        print(f"Generating {name} ({DURATION_SECONDS}s)...")
        generate_sound(prompt, out_path)
        size_kb = out_path.stat().st_size / 1024
        print(f"  Saved: {out_path} ({size_kb:.0f} KB)")
    print("\nDone — 8 ambience tracks in assets/ambience/")
