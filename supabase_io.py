"""Supabase-backed replacement for topic_agent.py's CSV queue + local-disk
storage for audio/script/thumbnail. Raw video is intentionally NOT persisted
here — it's rendered, uploaded to YouTube, then discarded (a single ~789MB
episode would burn most of Supabase Storage's free 1GB tier on its own).

Needs SUPABASE_URL and SUPABASE_SERVICE_KEY in .env (service_role key, not
anon — this runs server-side in CI/local scripts, not in a browser, and needs
write access). Falls back to raising a clear error if those aren't set yet,
rather than silently doing nothing.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

AUDIO_BUCKET = "narava-audio"
SCRIPTS_BUCKET = "narava-scripts"
THUMBNAILS_BUCKET = "narava-thumbnails"
IMAGES_BUCKET = "narava-images"

_client = None


def _require_client() -> Client:
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY not set in .env — "
            "complete Supabase project setup first (see supabase_setup/schema.sql)."
        )
    _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ---- Topic queue (mirrors agents/topic_agent.py's interface) ----

def get_next_topic():
    db = _require_client()
    res = db.table("topics").select("*").eq("status", "pending").order("id").limit(1).execute()
    return res.data[0] if res.data else None


def mark_topic_done(topic_id, video_id=""):
    db = _require_client()
    db.table("topics").update({"status": "published", "video_id": str(video_id)}).eq("id", topic_id).execute()


def mark_topic_failed(topic_id, reason=""):
    db = _require_client()
    db.table("topics").update({"status": "failed", "notes": str(reason)[:200]}).eq("id", topic_id).execute()


# ---- Pipeline run log (for the dashboard) ----

def run_start(topic_id, angle):
    db = _require_client()
    res = db.table("pipeline_runs").insert({
        "topic_id": topic_id, "angle": angle, "status": "running",
    }).execute()
    return res.data[0]["id"] if res.data else None


def run_update_agent(run_id, current_agent):
    if run_id is None:
        return
    db = _require_client()
    db.table("pipeline_runs").update({"current_agent": current_agent}).eq("id", run_id).execute()


def run_done(run_id):
    if run_id is None:
        return
    db = _require_client()
    db.table("pipeline_runs").update({"status": "done", "finished_at": "now()"}).eq("id", run_id).execute()


def run_failed(run_id, error):
    if run_id is None:
        return
    db = _require_client()
    db.table("pipeline_runs").update({
        "status": "failed", "error": str(error)[:500], "finished_at": "now()",
    }).eq("id", run_id).execute()


# ---- Storage: audio / script / thumbnail (NOT raw video) ----

def _upload(bucket, remote_path, local_path):
    db = _require_client()
    data = Path(local_path).read_bytes()
    db.storage.from_(bucket).upload(remote_path, data, {"upsert": "true"})


def _download(bucket, remote_path, local_path):
    db = _require_client()
    data = db.storage.from_(bucket).download(remote_path)
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_bytes(data)
    return local_path


# Free tier hard-caps individual file uploads at 50MB (confirmed live on the
# Narava org, 2026-06-20 — not just the 1GB total quota, a separate per-file
# limit that Pro removes for $25/mo). A full ~78min episode is ~113MB, so audio
# is split into <50MB chunks on upload and rejoined on download. MP3 is a
# frame-based format with no global header, so naive byte-level concatenation
# of sequential chunks reconstructs a valid, playable file.
AUDIO_CHUNK_BYTES = 40 * 1024 * 1024  # 40MB — comfortable margin under the 50MB cap


def upload_audio(topic_id, local_path):
    db = _require_client()
    data = Path(local_path).read_bytes()
    parts = [data[i:i + AUDIO_CHUNK_BYTES] for i in range(0, len(data), AUDIO_CHUNK_BYTES)] or [b""]
    for i, part in enumerate(parts):
        db.storage.from_(AUDIO_BUCKET).upload(f"{topic_id}_part{i:03d}.mp3", part, {"upsert": "true"})
    return len(parts)


def download_audio(topic_id, local_path):
    db = _require_client()
    chunks = []
    i = 0
    while True:
        try:
            chunks.append(db.storage.from_(AUDIO_BUCKET).download(f"{topic_id}_part{i:03d}.mp3"))
        except Exception:
            break
        i += 1
    if not chunks:
        raise FileNotFoundError(f"No audio parts found in Storage for topic {topic_id}")
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_bytes(b"".join(chunks))
    return local_path


def upload_script(topic_id, local_path):
    _upload(SCRIPTS_BUCKET, f"{topic_id}.txt", local_path)


def download_script(topic_id, local_path):
    return _download(SCRIPTS_BUCKET, f"{topic_id}.txt", local_path)


def upload_thumbnail(category, slug, variant, local_path):
    """Keyed by category/slug (matches get_manual_thumbnails() in assembly_agent.py,
    which looks up thumbnails/{category}/{slug}/A.ext — NOT by topic_id, so this
    stays consistent with the local-disk convention everything else already uses."""
    ext = Path(local_path).suffix
    remote_path = f"{category.lower()}/{slug.lower()}/{variant}{ext}"
    _upload(THUMBNAILS_BUCKET, remote_path, local_path)


def download_thumbnails(category, slug, local_dir):
    """Download whatever A/B thumbnail variants exist for category/slug into
    local_dir, recreating the structure get_manual_thumbnails() expects."""
    db = _require_client()
    remote_prefix = f"{category.lower()}/{slug.lower()}"
    entries = db.storage.from_(THUMBNAILS_BUCKET).list(remote_prefix)
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        data = db.storage.from_(THUMBNAILS_BUCKET).download(f"{remote_prefix}/{entry['name']}")
        (local_dir / entry["name"]).write_bytes(data)
    return local_dir


# ---- Images: synced into the SAME local folder structure assembly_agent.py
# already expects (images/{category}/{slug}/NN.ext) — this keeps assembly_agent.py
# untouched; only the CI job needs to pull images down before running create_video(). ----

def upload_topic_images(category, slug, local_dir):
    """Upload every image in local_dir (e.g. images/comparative/great_flood/) under
    a 'category/slug/filename' path, mirroring the local folder layout."""
    db = _require_client()
    local_dir = Path(local_dir)
    for img_path in sorted(local_dir.glob("*")):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        remote_path = f"{category.lower()}/{slug.lower()}/{img_path.name}"
        data = img_path.read_bytes()
        db.storage.from_(IMAGES_BUCKET).upload(remote_path, data, {"upsert": "true"})


def download_topic_images(category, slug, local_dir):
    """Download all images for category/slug into local_dir, recreating the same
    folder structure _get_images() in assembly_agent.py already expects."""
    db = _require_client()
    remote_prefix = f"{category.lower()}/{slug.lower()}"
    entries = db.storage.from_(IMAGES_BUCKET).list(remote_prefix)
    if not entries:
        raise FileNotFoundError(
            f"No images in Supabase Storage for {category}/{slug} — generate them via "
            f"Google Flow and run supabase_setup/sync_images_up.py first."
        )
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        remote_path = f"{remote_prefix}/{entry['name']}"
        data = db.storage.from_(IMAGES_BUCKET).download(remote_path)
        (local_dir / entry["name"]).write_bytes(data)
    return local_dir
