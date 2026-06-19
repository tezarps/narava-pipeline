#!/usr/bin/env python3
import os, sys
from dotenv import load_dotenv
load_dotenv()

from google import genai

key = (os.environ.get("GEMINI_API_KEY") or
       os.environ.get("GOOGLE_AI_STUDIO_KEY") or
       os.environ.get("GOOGLE_API_KEY"))

print("API key found:", bool(key))
if not key:
    print("→ Tambah GEMINI_API_KEY ke .env dulu")
    sys.exit(0)

client = genai.Client(api_key=key)

print("\nAvailable TTS models:")
for m in client.models.list():
    name = m.name if hasattr(m, 'name') else str(m)
    if any(x in name.lower() for x in ["tts", "speech"]):
        print(f"  {name}")

print("\nAll flash/pro models (3.x / 2.5):")
for m in client.models.list():
    name = m.name if hasattr(m, 'name') else str(m)
    if any(x in name for x in ["3.", "2.5"]):
        print(f"  {name}")
