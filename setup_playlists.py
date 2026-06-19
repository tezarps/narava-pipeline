#!/usr/bin/env python3
"""
Create the 4 Narava playlists on YouTube and save their IDs to playlist_ids.json.
Run once: python3 setup_playlists.py
"""
import json
import pickle
from pathlib import Path
from googleapiclient.discovery import build

TOKEN_FILE = Path(__file__).parent / "youtube_token.pickle"
PLAYLIST_IDS_FILE = Path(__file__).parent / "playlist_ids.json"

PLAYLISTS = [
    {
        "key": "greek",
        "title": "Greek Mythology Sleep Stories",
        "description": (
            "Fall asleep in ancient Greece. Servants, oracles, temple keepers — "
            "slow stories set in the world of the Greek gods. New episode nightly."
        ),
    },
    {
        "key": "norse",
        "title": "Norse Mythology Sleep Stories",
        "description": (
            "The mead halls are quiet. The fire is low. Drift to sleep in the "
            "Viking age — Asgard, Valhalla, the frozen Norse realms."
        ),
    },
    {
        "key": "egyptian",
        "title": "Egyptian Mythology Sleep Stories",
        "description": (
            "The Nile at night. Torch-lit temples. The priests walking in silence. "
            "Sleep stories from the world of ancient Egypt."
        ),
    },
    {
        "key": "all",
        "title": "Ancient World Sleep Stories — All Episodes",
        "description": (
            "Every story from Narava, in one place. Greek, Norse, Egyptian, "
            "Celtic and beyond. New episode added every night."
        ),
    },
    {
        "key": "comparative",
        "title": "Mythology Compared — Sleep Stories",
        "description": (
            "The same ancient stories, remembered differently across the world. "
            "Slow, comparative mythology for sleep — no answers, just old memories "
            "set side by side."
        ),
    },
]


def main():
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)

    youtube = build("youtube", "v3", credentials=creds)

    ids = {}
    try:
        ids = json.loads(PLAYLIST_IDS_FILE.read_text())
    except Exception:
        pass

    for pl in PLAYLISTS:
        if ids.get(pl["key"]):
            print(f"  ✓ {pl['title']} — already exists: {ids[pl['key']]}")
            continue

        resp = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": pl["title"],
                    "description": pl["description"],
                    "defaultLanguage": "en",
                },
                "status": {"privacyStatus": "public"},
            },
        ).execute()

        pid = resp["id"]
        ids[pl["key"]] = pid
        PLAYLIST_IDS_FILE.write_text(json.dumps(ids, indent=2))
        print(f"  ✓ Created: {pl['title']} → {pid}")

    print(f"\nPlaylist IDs saved to {PLAYLIST_IDS_FILE}")
    print(json.dumps(ids, indent=2))


if __name__ == "__main__":
    main()
