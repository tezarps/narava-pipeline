#!/usr/bin/env python3
"""Test Gemini 3.1 Flash TTS — voices & custom voice style."""
import os, wave, struct, subprocess
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
    "You had imagined the home of the gods to be filled with noise — "
    "thunderclaps, the clash of divine arguments, the endless movement of immortals with purpose. "
    "But as you climbed the final steps into the outer courtyard of Zeus's palace, "
    "what struck you first was the stillness. "
    "Stone columns rose on either side, pale as bone in the early morning light. "
    "The air was thin and cool, carrying the faint smell of cedar smoke "
    "from torches that had burned through the night."
)

def pcm_to_mp3(pcm_bytes, out_path, sample_rate=24000):
    """Convert raw PCM bytes → wav → mp3 via ffmpeg."""
    wav_path = out_path.with_suffix(".wav")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "192k", str(out_path)],
        capture_output=True, check=True
    )
    wav_path.unlink()

def generate(voice_name, style_prompt=None, label=None):
    label = label or voice_name
    out = OUT_DIR / f"{label}.mp3"

    text = SAMPLE_TEXT
    if style_prompt:
        # Prepend style instruction to the text
        text = f"<speak_style>{style_prompt}</speak_style>\n{SAMPLE_TEXT}"

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )
        audio_data = resp.candidates[0].content.parts[0].inline_data.data
        pcm_to_mp3(audio_data, out)
        print(f"  ✓ {label} → {out.name}")
    except Exception as e:
        print(f"  ✗ {label}: {e}")

# --- Test 1: deep male voices ---
print("=== Deep male voices ===")
for v in ["Charon", "Fenrir", "Orus", "Achird", "Algenib"]:
    generate(v)

# --- Test 2: custom style via prompt (voice prompting) ---
print("\n=== Custom style test (Charon + sleep narrator style) ===")
try:
    resp = client.models.generate_content(
        model=MODEL,
        contents=SAMPLE_TEXT,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
            system_instruction=(
                "You are a sleep story narrator. Speak slowly, warmly, and deeply. "
                "Your pace should be calm and unhurried — like someone telling a bedtime story "
                "to help a person drift off to sleep. Slightly lower your tone. Never rush."
            ),
        ),
    )
    audio_data = resp.candidates[0].content.parts[0].inline_data.data
    out = OUT_DIR / "Charon_sleep_style.mp3"
    pcm_to_mp3(audio_data, out)
    print(f"  ✓ Charon (sleep style) → {out.name}")
except Exception as e:
    print(f"  ✗ Custom style: {e}")

# --- Test 3: check if custom voice config exists ---
print("\n=== Checking CustomVoiceConfig availability ===")
try:
    cfg = types.VoiceConfig(
        prebuilt_voice_config=None,
    )
    attrs = [a for a in dir(cfg) if "custom" in a.lower() or "voice" in a.lower()]
    print("  VoiceConfig attrs:", attrs)
except Exception as e:
    print("  Error:", e)

print(f"\nDone. Open: {OUT_DIR}")
