#!/usr/bin/env python3
"""Generate a 30-second voice sample with Journey-D voice. Output to Desktop."""
import subprocess
from pathlib import Path
from google.cloud import texttospeech
from config import TTS_VOICE, TTS_SPEAKING_RATE, TTS_PITCH

SAMPLE_TEXT = """
The mountain was quieter than you expected.

You had imagined the home of the gods to be filled with noise — thunderclaps, the clash of divine arguments, the endless movement of immortals with purpose. But as you climbed the final steps into the outer courtyard of Zeus's palace, what struck you first was the stillness.

Stone columns rose on either side, pale as bone in the early morning light. The air was thin and cool, carrying the faint smell of cedar smoke from torches that had burned through the night and were now guttering low. Your sandals made almost no sound against the marble floor.

A senior servant appeared from the shadows between two pillars. She was perhaps fifty years old, with silver-streaked hair pinned back severely, and she looked at you with the calm, unimpressed expression of someone who had spent thirty years in this place and found very little left surprising.

"You are the new one," she said. It was not a question.

You said that you were.

She handed you a cloth — rough linen, not the fine fabric you might have hoped for — and gestured toward a row of oil lamps along the far wall. "Those," she said, "before he wakes."
"""

OUT = Path.home() / "Desktop" / "narava_voice_sample.mp3"

client = texttospeech.TextToSpeechClient()
synthesis_input = texttospeech.SynthesisInput(text=SAMPLE_TEXT.strip())
voice = texttospeech.VoiceSelectionParams(language_code="en-US", name=TTS_VOICE)
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=TTS_SPEAKING_RATE,
    pitch=TTS_PITCH,
    effects_profile_id=["headphone-class-device"],
)

print(f"Generating sample with {TTS_VOICE} @ rate={TTS_SPEAKING_RATE}...")
response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

with open(OUT, "wb") as f:
    f.write(response.audio_content)

# Trim to 30 seconds
trimmed = Path.home() / "Desktop" / "narava_voice_sample_30s.mp3"
subprocess.run([
    "ffmpeg", "-y", "-i", str(OUT),
    "-t", "30", "-c:a", "libmp3lame", "-b:a", "192k",
    str(trimmed)
], capture_output=True)
OUT.unlink()

r = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", str(trimmed)],
    capture_output=True, text=True
)
print(f"Done → {trimmed}")
print(f"Duration: {float(r.stdout.strip()):.1f}s")
print(f"Voice: {TTS_VOICE}, rate: {TTS_SPEAKING_RATE}")
