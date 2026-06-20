"""Auto-generates the scene images a topic needs, via Nano Banana 2
(Gemini 3.1 Flash Image) — closes the last manual step in the pipeline
(previously: generate by hand in Google Flow, then run
supabase_setup/sync_images_up.py). Called from scheduler.py only when a
topic has no images locally and none in Supabase Storage yet.
"""
import base64
import json
import time
import urllib.request
import urllib.error

import anthropic
from config import ANTHROPIC_API_KEY, GEMINI_IMAGE_API_KEY, NANO_BANANA_MODEL, HAIKU_MODEL, IMAGES_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

IMAGE_COUNT = 12

_STYLE_SUFFIX = (
    ", cinematic painterly illustration, epic atmospheric lighting, "
    "wide shot, small figure in a vast ancient world, mythological art style, "
    "no text, no watermark, no modern elements"
)

_PROMPTS_SYSTEM = """You write short visual scene descriptions for a YouTube sleep-mythology \
channel. Given a topic and angle, output exactly {n} distinct visual scenes from that story, \
moving roughly chronologically (dawn to night), each a single vivid sentence describing a wide \
cinematic shot — location, light, mood, a small human figure dwarfed by an ancient space. \
No character close-ups, no dialogue, no modern objects. Return ONLY a JSON array of {n} strings, \
nothing else."""


def _generate_scene_prompts(topic, angle, n=IMAGE_COUNT):
    msg = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1500,
        system=_PROMPTS_SYSTEM.format(n=n),
        messages=[{"role": "user", "content": f"Topic: {topic}\nAngle: {angle}"}],
    )
    text = msg.content[0].text.strip()
    start, end = text.find("["), text.rfind("]")
    scenes = json.loads(text[start:end + 1])
    return scenes[:n]


def _call_nano_banana(prompt, retries=3):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{NANO_BANANA_MODEL}:generateContent?key={GEMINI_IMAGE_API_KEY}"
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt + _STYLE_SUFFIX}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            for cand in data.get("candidates", []):
                for part in cand["content"]["parts"]:
                    if "inlineData" in part:
                        return base64.b64decode(part["inlineData"]["data"])
            raise RuntimeError(f"No image in Nano Banana response: {data}")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Nano Banana {e.code}: {e.read().decode()}")
    raise RuntimeError("Nano Banana: exhausted retries")


def generate_images(topic, angle, category, slug, count=IMAGE_COUNT):
    """Generates `count` distinct scene images for a topic and writes them to
    images/{category}/{slug}/scene_NN.jpg. Returns the list of paths written."""
    out_dir = IMAGES_DIR / category.lower() / slug.lower()
    out_dir.mkdir(parents=True, exist_ok=True)

    scenes = _generate_scene_prompts(topic, angle, count)
    paths = []
    for i, scene_prompt in enumerate(scenes, start=1):
        img_bytes = _call_nano_banana(scene_prompt)
        out_path = out_dir / f"scene_{i:02d}.jpg"
        out_path.write_bytes(img_bytes)
        paths.append(out_path)
        print(f"    image {i}/{len(scenes)}: {scene_prompt[:70]}...")
    return paths
