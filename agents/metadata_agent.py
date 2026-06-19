import json
import anthropic
from pathlib import Path
from config import ANTHROPIC_API_KEY, HAIKU_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PLAYLIST_IDS_FILE = Path(__file__).parent.parent / "playlist_ids.json"
CHANNEL_URL = "https://www.youtube.com/@NaravaAI"

# Primary-source citation per category — adds genuine original-research signal to each
# description (directly counters YouTube's "lacks original insight" inauthentic-content
# criterion; see project memory project_narava_pipeline.md).
CATEGORY_SOURCES = {
    "greek": "Sourced from Homer's Iliad and Odyssey, Hesiod's Theogony, and Ovid's Metamorphoses.",
    "norse": "Sourced from the Poetic Edda and the Prose Edda.",
    "egyptian": "Sourced from the Pyramid Texts and the Egyptian Book of the Dead.",
    "japanese": "Sourced from the Kojiki and the Nihon Shoki.",
    "aztec": "Sourced from the Codex Chimalpopoca and colonial-era Nahua chronicles.",
    "celtic": "Sourced from the Mabinogion and early Irish mythological cycles.",
    "comparative": "Sourced from the Epic of Gilgamesh, the Book of Genesis, the Shatapatha Brahmana, Ovid's Metamorphoses, and the Shujing flood chronicles — five traditions, side by side.",
}


def _playlist_url(category):
    try:
        ids = json.loads(PLAYLIST_IDS_FILE.read_text())
        pid = ids.get(category.lower())
        if pid:
            return f"https://www.youtube.com/playlist?list={pid}"
    except Exception:
        pass
    return CHANNEL_URL


def _all_playlist_url():
    try:
        ids = json.loads(PLAYLIST_IDS_FILE.read_text())
        pid = ids.get("all")
        if pid:
            return f"https://www.youtube.com/playlist?list={pid}"
    except Exception:
        pass
    return CHANNEL_URL


def _timestamp_block(duration_min):
    if duration_min < 30:
        return "00:00 – The story begins"
    step = duration_min / 4
    marks = [0] + [int(step * i) for i in range(1, 4)] + [duration_min - 5]
    labels = ["The story begins", "Into the ancient world",
              "The heart of the tale", "Deep in the story", "The quiet hours"]
    def fmt(m):
        h, mn = divmod(m, 60)
        return f"{h}:{mn:02d}:00" if h else f"{mn:02d}:00"
    return "\n".join(f"{fmt(m)} – {l}" for m, l in zip(marks, labels))


_PROMPT = """You are an expert YouTube SEO strategist for a mythology sleep stories channel called "Narava Sleep Stories".

Your job: generate a highly optimized title, description, and tags for this video.

Topic: {topic}
Angle: {angle}
Category: {category} mythology
Duration: ~{duration_min} minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEO RULES — follow strictly:

TITLE rules:
- 65–80 characters total
- CRITICAL: the specific character/scene name + "for Sleep" must be fully readable within
  the FIRST 48 CHARACTERS — YouTube truncates search results/suggested-video tiles around
  48-60 characters, and the specific character name (e.g. "Zeus", "Poseidon") carries far
  more standalone search value than the generic mythology-type tag, so it must never be
  pushed past the truncation point. NEVER lead with the mythology type or a generic brand
  phrase — always lead with the specific character/scene.
- Must contain: exact phrase "for Sleep" AND the mythology type (Greek/Norse/Egyptian/Celtic/Japanese/Aztec)
- If character budget allows after the mythology type, append "Bedtime Story" — a
  high-frequency keyword phrase among top competitors in this niche
- Format that performs best: "[Specific Scene or Character] for Sleep | [Mythology Type] Bedtime Story"
- Examples of HIGH-performing titles in this niche:
  "Serving Zeus on Mount Olympus for Sleep | Greek Mythology Bedtime Story"
  "A Night in Valhalla for Sleep | Norse Mythology Bedtime Story"
  "Walking the Nile with Isis for Sleep | Egyptian Bedtime Story"
- NO clickbait, NO ALL CAPS, NO emojis in title

DESCRIPTION rules:
- First 125 characters are critical — shown in YouTube search snippets
- First line must be a calm, specific hook that matches sleep-seeker intent
- Naturally weave in: "[topic] sleep story", "sleep stories for adults", "mythology sleep"
- Write like a human, not a bot — specific and sensory, not generic
- Include "{duration_min}-minute" naturally in the text
- Structure: hook → scene-setting (sensory) → who it's for → timestamps → playlists → subscribe CTA → disclosure

TAGS rules:
- 15 tags total
- Mix: 3 ultra-broad, 6 mid-tail, 6 long-tail specific to this topic
- Ultra-broad: "sleep stories", "sleep stories for adults", "bedtime stories"
- Mid-tail: "{category} mythology sleep", "mythology sleep stories", "ancient {category} sleep story", "sleep meditation story", "{topic} sleep", "{category} mythology bedtime"
- Long-tail: variations specific to the exact topic and angle
- Order: most important first
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output EXACTLY this format, nothing else:

TITLE: [your optimized title]

DESCRIPTION:
[First line: 125-char hook matching search intent]

[2-3 sentences: specific sensory scene-setting — torchlight, stone, cold air, silence. Human voice.]

[1 sentence: who this is for — insomnia, winding down, falling asleep]

Narrated by Shelby.

{timestamp_block}

────────────────────────
More mythology sleep stories:
▶ {category_cap} Mythology → {category_url}
▶ All Episodes → {all_url}
▶ Full Channel → {channel_url}
────────────────────────

New mythology sleep story three times a week — Sunday, Wednesday, and Friday. Subscribe so you never miss one.

────────────────────────
These are fictional, imaginative retellings of ancient mythology — not historical fact. Made for sleep and relaxation. {source_note}
Narration and illustrations are AI-assisted; topic research, story structure, and final editing are human-curated.
────────────────────────

#SleepStories #MythologySleep #{category_cap}Mythology #{topic_tag}Sleep #SleepStoriesForAdults #BedtimeStories #AncientMythology #DeepSleep #SleepMeditation #MythologyBedtime

TAGS: [15 tags comma-separated, most important first]"""


def generate_metadata(topic_data, duration_min=60):
    topic_tag = topic_data["topic"].replace(" ", "")
    category = topic_data["category"]
    source_note = CATEGORY_SOURCES.get(category.lower(), "Sourced from traditional mythological texts.")
    r = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": _PROMPT.format(
            topic=topic_data["topic"],
            angle=topic_data["angle"],
            category=category,
            category_cap=category.capitalize(),
            category_url=_playlist_url(category),
            all_url=_all_playlist_url(),
            channel_url=CHANNEL_URL,
            topic_tag=topic_tag,
            duration_min=duration_min,
            timestamp_block=_timestamp_block(duration_min),
            source_note=source_note,
        )}],
    )

    text = r.content[0].text
    title, description, tags = "", "", []
    lines = text.strip().split("\n")
    mode = None
    desc_lines = []

    for line in lines:
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()[:100]
            mode = "title"
        elif line.startswith("DESCRIPTION:"):
            mode = "description"
        elif line.startswith("TAGS:"):
            description = "\n".join(desc_lines).strip()
            raw_tags = line.replace("TAGS:", "").strip()
            tags = [t.strip() for t in raw_tags.split(",")][:15]
            mode = "tags"
        elif mode == "description":
            desc_lines.append(line)

    if not description:
        description = "\n".join(desc_lines).strip()

    return {"title": title, "description": description, "tags": tags}
