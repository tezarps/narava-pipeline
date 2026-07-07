import json
import pickle
from datetime import datetime, timezone, timedelta
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_CLIENT_SECRET, TOKEN_FILE

PLAYLIST_IDS_FILE = Path(__file__).parent.parent / "playlist_ids.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# Optimal publish time: 8 PM US Eastern
# EDT (summer Mar-Nov) = UTC-4 | EST (winter Nov-Mar) = UTC-5
# 8 PM EDT = 07:00 WIB next day — prime time US sleep viewers
PUBLISH_HOUR = 20  # 8 PM

# Daily cadence (upgraded from 3x/week on 2026-07-06) — pipeline runs fully in
# the cloud now (GitHub Actions), so there's no local-Mac bottleneck limiting
# how often a topic can be produced. Only the content images are still a
# manual step (Google Flow); when they're not ready yet, scheduler.py pauses
# that topic cleanly (status "awaiting_images") and the same daily trigger
# picks it back up once they're uploaded — see project memory
# feedback_pipeline_no_autoloop.md. Python weekday(): Mon=0..Sun=6.
PUBLISH_WEEKDAYS = {0, 1, 2, 3, 4, 5, 6}  # every day


def _latest_scheduled_utc():
    """Latest still-future publish_at_utc already queued in schedule.json, or
    None. Only counts entries UPLOADED recently (last 3 days) as genuine
    collisions to avoid — old leftover entries from the pre-daily 2-3x/week
    cadence (e.g. a backlog video queued weeks ago for a date far in the
    future) must not push a brand-new upload's slot out by days. Confirmed
    2026-07-07: without this filter, a fresh Apollo re-upload got pushed to
    2026-07-12 because of a stale Great Flood entry from 2026-06-19 still
    sitting in schedule.json with publish_at_utc=2026-07-11."""
    import json
    schedule_file = TOKEN_FILE.parent / "schedule.json"
    if not schedule_file.exists():
        return None
    try:
        entries = json.loads(schedule_file.read_text())
    except Exception:
        return None
    now = datetime.now(timezone.utc)
    recency_cutoff = now - timedelta(days=3)
    future = []
    for e in entries:
        try:
            ts = datetime.strptime(e["publish_at_utc"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            uploaded = datetime.strptime(e["uploaded_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= now and uploaded >= recency_cutoff:
            future.append(ts)
    return max(future) if future else None


def _next_publish_time():
    """Return the next 8 PM US Eastern slot as UTC RFC3339, queued after any
    recently-scheduled (future) upload so videos publish on the daily cadence
    without two uploads landing on the same day."""
    # Detect if US East is currently on EDT (UTC-4) or EST (UTC-5)
    # Simple approach: use UTC offset based on month (EDT: Mar-Nov, EST: Nov-Mar)
    month = datetime.now(timezone.utc).month
    et_offset = -4 if 3 <= month <= 11 else -5
    et_zone = timezone(timedelta(hours=et_offset))
    label = "EDT" if et_offset == -4 else "EST"

    now_et = datetime.now(et_zone)
    target = now_et.replace(hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    if now_et >= target:
        target += timedelta(days=1)

    latest = _latest_scheduled_utc()
    if latest is not None:
        latest_et = latest.astimezone(et_zone)
        if target <= latest_et:
            target = latest_et + timedelta(days=1)

    while target.weekday() not in PUBLISH_WEEKDAYS:
        target += timedelta(days=1)

    utc_str = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    wib = target.astimezone(timezone(timedelta(hours=7)))
    return utc_str, f"{target.strftime('%H:%M')} {label} = {wib.strftime('%H:%M')} WIB"


def get_credentials():
    """Public so other scripts (e.g. ab_test_check.py) can build their own
    service — e.g. youtubeAnalytics v2 — off the same token without reaching
    into a private function's internals."""
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except Exception as e:
                # Refresh token itself revoked/expired (not just the access
                # token) — fall back to a fresh browser OAuth flow instead of
                # crashing here. Confirmed 2026-07-07: a stale refresh token
                # made this raise invalid_grant and abort setup_youtube_auth.py
                # before it ever got a chance to open the browser.
                print(f"    Refresh failed ({e}) — starting fresh OAuth flow...")
        if not refreshed:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
            # prompt=select_account forces Google's account chooser instead of
            # silently reusing whatever Google session is already active in the
            # browser — confirmed 2026-07-07: without this, a fresh OAuth flow
            # silently authenticated as the wrong channel ("Tezarism" instead of
            # "NaravaAI", a separate Google account) because the browser already
            # had a Tezarism session logged in.
            creds = flow.run_local_server(port=8080, prompt="select_account")
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return creds


def _get_service():
    return build("youtube", "v3", credentials=get_credentials())


def _add_to_playlist(yt, video_id, playlist_id):
    if not playlist_id:
        return
    try:
        yt.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute()
    except Exception as e:
        print(f"    Warning: failed to add to playlist {playlist_id}: {e}")


def upload_video(video_path, thumbnail_path, metadata, category=None):
    yt = _get_service()
    publish_at_utc, publish_at_label = _next_publish_time()

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "24",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_utc,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=50 * 1024 * 1024,
    )

    request = yt.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"    Upload: {pct}%", end="\r")

    video_id = response["id"]
    print(f"    Uploaded: youtube.com/watch?v={video_id}")
    print(f"    Scheduled: {publish_at_label}")

    # Save the schedule slot BEFORE the thumbnail step — a thumbnail failure
    # (e.g. file over YouTube's 2MB limit) must never leave this publish slot
    # untracked, or the next upload's queue logic won't see it and will
    # collide on the same date.
    _save_schedule(video_id, metadata, publish_at_utc, publish_at_label)

    if thumbnail_path and Path(thumbnail_path).exists():
        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path)),
        ).execute()
        print("    Thumbnail set")

    if category:
        try:
            ids = json.loads(PLAYLIST_IDS_FILE.read_text())
        except Exception:
            ids = {}
        cat_pid = ids.get(category.lower())
        all_pid = ids.get("all")
        if cat_pid:
            _add_to_playlist(yt, video_id, cat_pid)
            print(f"    Added to playlist: {category}")
        if all_pid:
            _add_to_playlist(yt, video_id, all_pid)
            print(f"    Added to playlist: all")

    return video_id


def _save_schedule(video_id, metadata, publish_at_utc, publish_at_label):
    schedule_file = TOKEN_FILE.parent / "schedule.json"
    entries = []
    if schedule_file.exists():
        try:
            entries = json.loads(schedule_file.read_text())
        except Exception:
            pass
    entries.insert(0, {
        "video_id": video_id,
        "title": metadata.get("title", ""),
        "publish_at_utc": publish_at_utc,
        "publish_at_label": publish_at_label,
        "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "status": "scheduled",
    })
    entries = entries[:60]
    schedule_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
