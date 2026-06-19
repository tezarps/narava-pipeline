#!/usr/bin/env python3
"""Test Gemini TTS: replicated_voice_config & style prompting."""
import os, wave, subprocess, inspect
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

KEY = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=KEY)
MODEL = "gemini-3.1-flash-tts-preview"
OUT_DIR = Path.home() / "Desktop" / "narava_tts_test"
OUT_DIR.mkdir(exist_ok=True)

SAMPLE_TEXT = (
    "The mountain was quieter than you expected. "
    "You had imagined the home of the gods to be filled with noise. "
    "But as you climbed the final steps into the outer courtyard, "
    "what struck you first was the stillness. "
    "Stone columns rose on either side, pale as bone in the early morning light. "
    "The air was thin and cool, carrying the faint smell of cedar smoke "
    "from torches that had burned through the night."
)

def pcm_to_mp3(pcm_bytes, out_path, sample_rate=24000):
    wav = out_path.with_suffix(".wav")
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-b:a", "192k", str(out_path)],
                   capture_output=True, check=True)
    wav.unlink()

def gen(voice_name, text, label):
    out = OUT_DIR / f"{label}.mp3"
    resp = client.models.generate_content(
        model=MODEL, contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        ),
    )
    pcm_to_mp3(resp.candidates[0].content.parts[0].inline_data.data, out)
    print(f"  ✓ {label}")

# --- Test replicated_voice_config structure ---
print("=== ReplicatedVoiceConfig inspect ===")
try:
    rvc = types.ReplicatedVoiceConfig
    print("  Fields:", list(rvc.model_fields.keys()) if hasattr(rvc, 'model_fields') else inspect.signature(rvc))
except Exception as e:
    print("  Error:", e)

# --- Style via content prompt (no system_instruction) ---
print("\n=== Style prompting via content ===")
styles = [
    ("Speak very slowly, deeply and warmly. You are a sleep story narrator telling an ancient tale to help someone drift off. Pause between sentences.\n\n" + SAMPLE_TEXT,
     "Charon", "Charon_style_content"),
    ("Read this as a calm, slow bedtime story narrator. Deep voice. Unhurried. Soothing.\n\n" + SAMPLE_TEXT,
     "Orus", "Orus_style_content"),
]
for text, voice, label in styles:
    try:
        gen(voice, text, label)
    except Exception as e:
        print(f"  ✗ {label}: {e}")

# --- Test replicated_voice_config with audio reference ---
print("\n=== ReplicatedVoiceConfig test ===")
# Check if we can use an audio file as voice reference
ref_audio = OUT_DIR / "Charon.mp3"
if ref_audio.exists():
    try:
        # Upload the reference audio first
        uploaded = client.files.upload(file=str(ref_audio), config={"mime_type": "audio/mpeg"})
        print(f"  Uploaded reference: {uploaded.name}")

        resp = client.models.generate_content(
            model=MODEL,
            contents=SAMPLE_TEXT,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        replicated_voice_config=types.ReplicatedVoiceConfig(
                            audio_file_uri=uploaded.uri if hasattr(uploaded, 'uri') else uploaded.name
                        )
                    )
                ),
            ),
        )
        pcm_to_mp3(resp.candidates[0].content.parts[0].inline_data.data,
                   OUT_DIR / "Charon_replicated.mp3")
        print("  ✓ Charon_replicated (voice clone from sample)")
    except Exception as e:
        print(f"  ✗ replicated_voice_config: {e}")
        # Try alternate param names
        print(f"     ReplicatedVoiceConfig fields: {[f for f in dir(types.ReplicatedVoiceConfig) if not f.startswith('_')]}")

print(f"\nDone → {OUT_DIR}")
