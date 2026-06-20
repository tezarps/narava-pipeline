#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import supabase_io as sb
from agents.script_agent import generate_script
from agents.tts_agent import generate_audio
from agents.assembly_agent import create_video, create_thumbnail, get_manual_thumbnails
from agents.metadata_agent import generate_metadata
from agents.upload_agent import upload_video
from status_manager import (
    agent_start, agent_done, agent_error,
    run_start, run_done, run_failed,
)
from config import OUTPUT_DIR, IMAGES_DIR
from telegram_notify import notify

THUMBNAILS_DIR = Path(__file__).parent / "thumbnails"


def _has_local_images(local_dir):
    return local_dir.exists() and any(p.suffix.lower() in (".jpg", ".jpeg", ".png") for p in local_dir.glob("*"))


def _ensure_local_images(category, slug):
    """Pull images down from Supabase Storage if they're not already on disk —
    a fresh GitHub Actions checkout has none (images/ is gitignored, never
    committed; assets live in Supabase Storage instead, pushed there via
    supabase_setup/sync_images_up.py after each Google Flow batch)."""
    local_dir = IMAGES_DIR / category.lower() / slug.lower()
    if _has_local_images(local_dir):
        return
    print(f"    No local images for {category}/{slug} — pulling from Supabase Storage...")
    sb.download_topic_images(category, slug, local_dir)


def _ensure_local_thumbnails(category, slug):
    local_dir = THUMBNAILS_DIR / category.lower() / slug.lower()
    if _has_local_images(local_dir):
        return
    try:
        sb.download_thumbnails(category, slug, local_dir)
    except Exception:
        pass  # no manual thumbnail synced yet — falls back to auto-generated


def _cleanup(topic_id, failed_stage):
    """Only clean up artifacts belonging to the stage that actually failed —
    never delete a finished audio.mp3 (real ElevenLabs credits paid for it)
    just because a later stage like architect/herald/messenger broke."""
    if failed_stage == "voice":
        # No finished audio yet at this point — safe to drop partial chunks.
        import shutil
        chunk_dir = OUTPUT_DIR / "audio" / f"chunks_{topic_id}"
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir)
        return

    if failed_stage == "architect":
        for f in [OUTPUT_DIR / "video" / f"{topic_id}.mp4", OUTPUT_DIR / "video" / f"{topic_id}_thumb.jpg"]:
            if f.exists():
                f.unlink()


def run(audio_only=False):
    print(f"\n{'='*52}")
    print(f"  Narava AI Pipeline  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if audio_only:
        print(f"  [AUDIO TEST MODE — stops after voice]")
    print(f"{'='*52}\n")

    topic = sb.get_next_topic()
    if not topic:
        print("No pending topics in Supabase `topics` table.")
        return

    topic_id = int(topic["id"])
    angle = topic["angle"]
    topic_slug = topic["topic"].lower().replace(" ", "_")
    started_at = datetime.now().isoformat()

    print(f"Topic ID : {topic_id}")
    print(f"Category : {topic['category']}")
    print(f"Angle    : {angle}\n")

    run_start(topic_id, angle)
    sb_run_id = sb.run_start(topic_id, angle)
    notify(f"🔱 Narava — started\nTopic #{topic_id}: {topic['topic']} ({topic['category']})\n{angle}")

    current_agent = "oracle"
    try:
        print("[1/6] The Oracle — selecting topic...")
        agent_done("oracle", f"Topic #{topic_id}: {topic['topic']}", payload={
            "id": topic_id,
            "category": topic["category"],
            "topic": topic["topic"],
            "angle": topic["angle"],
        })
        sb.run_update_agent(sb_run_id, "oracle")

        current_agent = "scribe"
        script_path = OUTPUT_DIR / "scripts" / f"{topic_id}.txt"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        if script_path.exists():
            print("[2/6] The Scribe — using cached local script (no API call)...")
            script = script_path.read_text(encoding="utf-8")
            agent_done("scribe", f"{len(script.split()):,} words (cached)")
        else:
            try:
                sb.download_script(topic_id, script_path)
                script = script_path.read_text(encoding="utf-8")
                print("[2/6] The Scribe — using script cached in Supabase (no API call)...")
                agent_done("scribe", f"{len(script.split()):,} words (cached in Supabase)")
            except Exception:
                print("[2/6] The Scribe — writing script...")
                agent_start("scribe", "Drafting with Haiku...")
                sb.run_update_agent(sb_run_id, "scribe")
                script = generate_script(topic)
                script_path.write_text(script, encoding="utf-8")
                sb.upload_script(topic_id, script_path)
                agent_done("scribe", f"{len(script.split()):,} words written")

        # In audio-only mode, take first 550 words as sample
        tts_script = " ".join(script.split()[:550]) if audio_only else script

        current_agent = "voice"
        print("\n[3/6] The Voice — narrating story...")
        if audio_only:
            print("    [SAMPLE: first 550 words only]")
        agent_start("voice", "Converting to audio...")
        sb.run_update_agent(sb_run_id, "voice")
        audio_path = generate_audio(tts_script, topic_id, category=topic["category"])
        if not audio_only:
            sb.upload_audio(topic_id, audio_path)
        agent_done("voice", f"Audio ready: {audio_path.name}")

        if audio_only:
            print(f"\n⏸ Audio sample ready: {audio_path}")
            print(f"  Listen and approve, then run: python3 scheduler.py")
            return audio_path

        current_agent = "architect"
        print("\n[4/6] The Architect — assembling video...")
        agent_start("architect", "Running FFmpeg...")
        sb.run_update_agent(sb_run_id, "architect")
        _ensure_local_images(topic["category"], topic_slug)
        _ensure_local_thumbnails(topic["category"], topic_slug)
        video_path, raw_thumb, duration_sec = create_video(audio_path, topic["category"], topic_id, topic_slug=topic_slug)
        size_mb = video_path.stat().st_size / 1024 / 1024
        agent_done("architect", f"Video ready: {size_mb:.0f}MB")

        current_agent = "herald"
        print("\n[5/6] The Herald — crafting metadata...")
        agent_start("herald", "Writing SEO title & description...")
        sb.run_update_agent(sb_run_id, "herald")
        duration_min = int(duration_sec / 60)
        metadata = generate_metadata(topic, duration_min=duration_min)
        meta_path = OUTPUT_DIR / "metadata" / f"{topic_id}.json"
        meta_path.parent.mkdir(exist_ok=True)
        import json as _json
        meta_path.write_text(_json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        agent_done("herald", metadata["title"][:60])
        print(f"    Title: {metadata['title']}")

        # Thumbnail: prefer manual A.jpg from thumbnails folder, fallback to auto-generate
        thumb_a, thumb_b = get_manual_thumbnails(topic["category"], topic_slug)
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
        sb.run_update_agent(sb_run_id, "messenger")
        video_id = upload_video(video_path, thumbnail_path, metadata, category=topic["category"])
        agent_done("messenger", f"youtube.com/watch?v={video_id}")

        mark_topic_done = sb.mark_topic_done
        mark_topic_done(topic_id, video_id)
        run_done(topic_id, angle, video_id, started_at)
        sb.run_done(sb_run_id)
        print(f"\n✓ Complete — youtube.com/watch?v={video_id}")
        notify(f"✅ Narava — published\n{topic['topic']} ({topic['category']})\nyoutube.com/watch?v={video_id}")
        if thumb_b:
            print(f"⚡ A/B Test: upload thumbnail B manually →")
            print(f"   https://studio.youtube.com/video/{video_id}/edit → Thumbnail → Test & Compare")
            print(f"   File: {thumb_b}")
        print()

    except Exception as e:
        agent_error(current_agent, e)
        print(f"\n✗ Failed at [{current_agent}]: {e}")
        traceback.print_exc()
        sb.mark_topic_failed(topic_id, e)
        run_failed(topic_id, angle, e, started_at)
        sb.run_failed(sb_run_id, e)
        notify(f"❌ Narava — failed at [{current_agent}]\nTopic #{topic_id}: {topic['topic']}\n{str(e)[:300]}")
        _cleanup(topic_id, current_agent)


if __name__ == "__main__":
    run(audio_only="--test-audio" in sys.argv)
