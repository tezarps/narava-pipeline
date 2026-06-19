#!/usr/bin/env python3
"""Redo Zeus end-to-end with 3.1 Achird (real audio, was 2.5 Flash). Cached script reused."""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from agents.topic_agent import mark_topic_done, mark_topic_failed
from agents.tts_agent import generate_audio
from agents.assembly_agent import create_video, create_thumbnail, get_manual_thumbnails
from agents.metadata_agent import generate_metadata
from agents.upload_agent import upload_video
from status_manager import agent_start, agent_done, agent_error, run_start, run_done, run_failed
from config import OUTPUT_DIR
import pandas as pd

topic_id = 1
df = pd.read_csv("topics/mythology_topics.csv")
row = df[df["id"] == topic_id].iloc[0].to_dict()
angle = row["angle"]
started_at = datetime.now().isoformat()
run_start(topic_id, angle)

script_path = OUTPUT_DIR / "scripts" / f"{topic_id}.txt"
script = script_path.read_text(encoding="utf-8")
agent_done("scribe", f"{len(script.split()):,} words (cached)")

current_agent = "voice"
try:
    print("\n[3/6] The Voice — re-narrating with 3.1 Achird...")
    agent_start("voice", "Converting to audio (3.1)...")
    audio_path = generate_audio(script, topic_id)
    agent_done("voice", f"Audio ready: {audio_path.name}")

    current_agent = "architect"
    print("\n[4/6] The Architect — assembling video...")
    agent_start("architect", "Running FFmpeg...")
    video_path, raw_thumb, duration_sec = create_video(
        audio_path, row["category"], topic_id,
        topic_slug=row["topic"].lower().replace(" ", "_")
    )
    size_mb = video_path.stat().st_size / 1024 / 1024
    agent_done("architect", f"Video ready: {size_mb:.0f}MB")

    current_agent = "herald"
    print("\n[5/6] The Herald — crafting metadata...")
    agent_start("herald", "Writing SEO title & description...")
    duration_min = int(duration_sec / 60)
    metadata = generate_metadata(row, duration_min=duration_min)
    meta_path = OUTPUT_DIR / "metadata" / f"{topic_id}.json"
    meta_path.parent.mkdir(exist_ok=True)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    agent_done("herald", metadata["title"][:60])
    print(f"    Title: {metadata['title']}")

    topic_slug = row["topic"].lower().replace(" ", "_")
    thumb_a, thumb_b = get_manual_thumbnails(row["category"], topic_slug)
    if thumb_a:
        thumbnail_path = thumb_a
        print(f"    Thumbnail: manual A — {thumb_a.name}")
    else:
        thumb_out = video_path.parent / f"{topic_id}_thumb.jpg"
        thumbnail_path = create_thumbnail(raw_thumb, metadata["title"], thumb_out)
        print(f"    Thumbnail: auto-generated — {thumb_out.name}")

    current_agent = "messenger"
    print("\n[6/6] The Messenger — uploading NEW video to YouTube...")
    agent_start("messenger", "Uploading...")
    video_id = upload_video(video_path, thumbnail_path, metadata)
    agent_done("messenger", f"youtube.com/watch?v={video_id}")

    mark_topic_done(topic_id, video_id)
    run_done(topic_id, angle, video_id, started_at)
    print(f"\n✓ Complete — youtube.com/watch?v={video_id}")
    print(f"⚠ OLD video (2.5 Flash audio) is now orphaned — delete manually via YouTube Studio if still present.")
    print()

except Exception as e:
    import traceback
    agent_error(current_agent, e)
    print(f"\n✗ Failed at [{current_agent}]: {e}")
    traceback.print_exc()
    mark_topic_failed(topic_id, e)
    run_failed(topic_id, angle, e, started_at)
