#!/usr/bin/env python3
"""Regenerate Poseidon's script (new Shelby intro) + audio only — stop before
Architect since images aren't ready yet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.script_agent import generate_script
from agents.tts_agent import generate_audio
from status_manager import agent_start, agent_done
from config import OUTPUT_DIR
import pandas as pd

topic_id = 3
df = pd.read_csv("topics/mythology_topics.csv")
row = df[df["id"] == topic_id].iloc[0].to_dict()

print("[2/6] The Scribe — writing script (with Shelby intro)...")
agent_start("scribe", "Drafting with Haiku...")
script = generate_script(row)
script_path = OUTPUT_DIR / "scripts" / f"{topic_id}.txt"
script_path.write_text(script, encoding="utf-8")
agent_done("scribe", f"{len(script.split()):,} words written")

print("\n[3/6] The Voice — narrating with Shelby...")
agent_start("voice", "Converting to audio...")
audio_path = generate_audio(script, topic_id)
agent_done("voice", f"Audio ready: {audio_path.name}")
print(f"\n✓ Done — {audio_path}")
