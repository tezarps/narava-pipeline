#!/usr/bin/env python3
"""Poseidon: script + audio (Shelby) already done — resume from Architect.
Schedule manually targets the next Wednesday per user's explicit request."""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from agents.topic_agent import mark_topic_done, mark_topic_failed
from agents.assembly_agent import create_video, create_thumbnail, get_manual_thumbnails
from agents.metadata_agent import generate_metadata
import agents.upload_agent as upload_agent
from status_manager import agent_start, agent_done, agent_error, run_start, run_done, run_failed
from config import OUTPUT_DIR
import pandas as pd

topic_id = 3
df = pd.read_csv("topics/mythology_topics.csv")
row = df[df["id"] == topic_id].iloc[0].to_dict()
angle = row["angle"]
audio_path = OUTPUT_DIR / "audio" / f"{topic_id}.mp3"
started_at = datetime.now().isoformat()
run_start(topic_id, angle)

# Pin publish to the next Wednesday (user's explicit request), independent of
# whatever's recorded in schedule.json (Hera's slot is being moved manually).
def _next_wednesday_8pm_et():
    month = datetime.now(timezone.utc).month
    et_offset = -4 if 3 <= month <= 11 else -5
    et_zone = timezone(timedelta(hours=et_offset))
    label = "EDT" if et_offset == -4 else "EST"
    now_et = datetime.now(et_zone)
    target = now_et.replace(hour=20, minute=0, second=0, microsecond=0)
    if now_et >= target:
        target += timedelta(days=1)
    while target.weekday() != 2:  # Wednesday
        target += timedelta(days=1)
    utc_str = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    wib = target.astimezone(timezone(timedelta(hours=7)))
    return utc_str, f"{target.strftime('%H:%M')} {label} = {wib.strftime('%H:%M')} WIB"

upload_agent._next_publish_time = _next_wednesday_8pm_et

current_agent = "architect"
try:
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
    print("\n[6/6] The Messenger — uploading to YouTube...")
    agent_start("messenger", "Uploading...")
    video_id = upload_agent.upload_video(video_path, thumbnail_path, metadata)
    agent_done("messenger", f"youtube.com/watch?v={video_id}")

    mark_topic_done(topic_id, video_id)
    run_done(topic_id, angle, video_id, started_at)
    print(f"\n✓ Complete — youtube.com/watch?v={video_id}")
    if thumb_b:
        print(f"⚡ A/B Test: upload thumbnail B manually →")
        print(f"   File: {thumb_b}")
    print()

except Exception as e:
    import traceback
    agent_error(current_agent, e)
    print(f"\n✗ Failed at [{current_agent}]: {e}")
    traceback.print_exc()
    mark_topic_failed(topic_id, e)
    run_failed(topic_id, angle, e, started_at)
