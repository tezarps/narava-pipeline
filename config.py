import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", "youtube_client_secret.json")

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
OUTPUT_DIR = BASE_DIR / "output"
TOPICS_FILE = BASE_DIR / "topics" / "mythology_topics.csv"
TOKEN_FILE = BASE_DIR / "youtube_token.pickle"

GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_VOICE = "Achird"

ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_VOICE_ID = "Hd8mWkf5kvyBZB0S7yXU"  # Ron - Older American Story Teller
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.3,
    "similarity_boost": 0.8,
    "style": 0.4,
    "speed": 0.85,  # slower, flowing delivery for sleep narration (range 0.7-1.2, 1.0=normal)
    "use_speaker_boost": True,
}

# Separate narrator for the "comparative" mythology line only (see project memory
# project_narava_pipeline.md) — distinct voice from the main single-deity Shelby
# narration, picked 2026-06-19 from ElevenLabs Voice Library.
# https://elevenlabs.io/app/voice-library?voiceId=auq43ws1oslv0tO4BDa7
COMPARATIVE_VOICE_ID = "auq43ws1oslv0tO4BDa7"
COMPARATIVE_VOICE_SETTINGS = {
    "stability": 0.25,       # lower = more expressive/varied intonation (storyteller, not flat reader)
    "similarity_boost": 0.85,
    "style": 0.55,           # lean into the voice's natural storyteller style exaggeration
    "speed": 0.88,           # slow for sleep content, but not so slow it kills expressiveness
    "use_speaker_boost": True,
}

# Uncompressed PCM (pcm_44100) requires ElevenLabs Pro tier ($99/mo) — confirmed via
# a failed live call on 2026-06-19 (403 subscription_required) while on Creator
# ($22/mo). Falling back to the highest-quality lossy format Creator supports until
# a tier decision is made; see project memory project_narava_pipeline.md.
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_192"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "audio").mkdir(exist_ok=True)
(OUTPUT_DIR / "video").mkdir(exist_ok=True)
