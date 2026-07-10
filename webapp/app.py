import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
import supabase_io as sb

TOPICS_FILE = BASE / "topics" / "mythology_topics.csv"
STATUS_FILE = BASE / "pipeline_status.json"
SCHEDULE_FILE = BASE / "schedule.json"
LOG_FILE = BASE / "logs" / "pipeline.log"
OUTPUT_DIR = BASE / "output"
IMAGE_PROMPTS_FILE = BASE / "content_plan_jun_jul_2026" / "image_prompts.json"
IMAGES_DIR = BASE / "images"
LOG_FILE.parent.mkdir(exist_ok=True)

_HTML = (Path(__file__).parent / "templates" / "index.html").read_text()

app = FastAPI(title="Narava AI Pipeline")


# ── HTML ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_HTML)


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    return {"agents": {}, "runs": [], "current_run": None}


@app.get("/api/topics")
def api_topics(status: str = "all"):
    df = pd.read_csv(TOPICS_FILE)
    if status != "all":
        df = df[df["status"] == status]
    df = df.fillna("")
    return df.to_dict(orient="records")


@app.post("/api/topics")
async def api_add_topic(request: Request):
    body = await request.json()
    df = pd.read_csv(TOPICS_FILE)
    df = df.fillna("")
    new_id = int(df["id"].max()) + 1 if not df.empty else 1
    new_row = {
        "id": new_id,
        "category": body.get("category", "greek").lower(),
        "topic": body.get("topic", ""),
        "angle": body.get("angle", ""),
        "status": "pending",
        "video_id": "",
        "notes": "",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(TOPICS_FILE, index=False)
    return new_row


@app.put("/api/topics/{topic_id}/reset")
def api_reset_topic(topic_id: int):
    df = pd.read_csv(TOPICS_FILE)
    df.fillna("", inplace=True)
    if topic_id not in df["id"].values:
        raise HTTPException(404, "Topic not found")
    df.loc[df["id"] == topic_id, "status"] = "pending"
    df.loc[df["id"] == topic_id, "notes"] = ""
    df.to_csv(TOPICS_FILE, index=False)
    return {"ok": True}


@app.delete("/api/topics/{topic_id}")
def api_delete_topic(topic_id: int):
    df = pd.read_csv(TOPICS_FILE)
    df = df[df["id"] != topic_id]
    df.to_csv(TOPICS_FILE, index=False)
    return {"ok": True}


@app.get("/api/stats")
def api_stats():
    df = pd.read_csv(TOPICS_FILE).fillna("")
    status_data = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    runs = status_data.get("runs", [])
    today = datetime.now().strftime("%Y-%m-%d")
    published_today = len({
        r.get("id") for r in runs
        if r.get("status") == "published" and r.get("started_at", "").startswith(today)
    })
    return {
        "total": len(df),
        "pending": int((df["status"] == "pending").sum()),
        "published": int((df["status"] == "published").sum()),
        "failed": int((df["status"] == "failed").sum()),
        "published_today": published_today,
        "total_runs": len(runs),
    }


@app.get("/api/schedule")
def api_schedule():
    entries = []
    if SCHEDULE_FILE.exists():
        try:
            entries = json.loads(SCHEDULE_FILE.read_text())
        except Exception:
            pass
    now_utc = datetime.utcnow().isoformat() + "Z"
    upcoming = [e for e in entries if e.get("publish_at_utc", "") > now_utc]
    past = [e for e in entries if e.get("publish_at_utc", "") <= now_utc]
    return {"upcoming": upcoming, "past": past}


@app.get("/api/image-prompts")
def api_image_prompts():
    """Topics currently blocked on manually-generated (Google Flow) images —
    queried live from Supabase (the real source of truth, not the stale local
    CSV) and cross-referenced with content_plan_jun_jul_2026/image_prompts.json
    for the ready-to-paste theme + 10 scene prompts, so the user can copy them
    straight from the webapp instead of digging through chat history."""
    prompts = {}
    if IMAGE_PROMPTS_FILE.exists():
        prompts = json.loads(IMAGE_PROMPTS_FILE.read_text())

    db = sb._require_client()
    # "awaiting_images" is always genuinely paused. A "failed"/"pending" topic
    # only counts as paused-on-images if it already has a drafted prompt below
    # (i.e. it's next-in-queue, not just one of dozens of far-future backlog
    # topics that haven't been worked on yet) — keeps this list to what the
    # user actually needs to act on today, not the whole 50-topic backlog.
    topics = db.table("topics").select("id,category,topic,angle,status").in_(
        "id", [int(k) for k in prompts.keys()]
    ).execute().data
    awaiting = db.table("topics").select("id,category,topic,angle,status").eq(
        "status", "awaiting_images"
    ).execute().data
    seen = {t["id"] for t in topics}
    topics += [t for t in awaiting if t["id"] not in seen]
    topics.sort(key=lambda t: t["id"])

    out = []
    for t in topics:
        local_dir = IMAGES_DIR / t["category"].lower() / t["topic"].lower().replace(" ", "_")
        has_images = local_dir.exists() and any(
            p.suffix.lower() in (".jpg", ".jpeg", ".png") for p in local_dir.glob("*")
        )
        if has_images:
            continue
        entry = prompts.get(str(t["id"]))
        out.append({
            "id": t["id"],
            "category": t["category"],
            "topic": t["topic"],
            "angle": t["angle"],
            "status": t["status"],
            "has_prompt": entry is not None,
            "theme": entry["theme"] if entry else "",
            "scenes": entry["scenes"] if entry else [],
        })
    return out


@app.get("/api/logs")
def api_logs(lines: int = 80):
    if not LOG_FILE.exists():
        return {"lines": []}
    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    all_lines = text.strip().split("\n")
    return {"lines": all_lines[-lines:]}


@app.get("/api/output/script/{topic_id}")
def api_output_script(topic_id: int):
    path = OUTPUT_DIR / "scripts" / f"{topic_id}.txt"
    if not path.exists():
        raise HTTPException(404, "Script not saved yet")
    return {"topic_id": topic_id, "script": path.read_text(encoding="utf-8")}


@app.get("/api/output/metadata/{topic_id}")
def api_output_metadata(topic_id: int):
    path = OUTPUT_DIR / "metadata" / f"{topic_id}.json"
    if not path.exists():
        raise HTTPException(404, "Metadata not saved yet")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/logs/stream")
async def api_logs_stream():
    async def event_stream():
        if not LOG_FILE.exists():
            yield "data: No log file yet.\n\n"
            return
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    await asyncio.sleep(2)
    return StreamingResponse(event_stream(), media_type="text/event-stream")
