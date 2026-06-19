import sys; sys.path.insert(0, '.')
from agents.tts_agent import generate_audio
from agents.assembly_agent import create_video, create_thumbnail
from agents.metadata_agent import generate_metadata
from agents.topic_agent import get_next_topic
from agents.upload_agent import upload_video
from config import GEMINI_API_KEY, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE
print("All imports OK")
print(f"TTS: {GEMINI_TTS_VOICE} via {GEMINI_TTS_MODEL}")
