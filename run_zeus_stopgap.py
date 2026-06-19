#!/usr/bin/env python3
"""One-off: run Zeus through the pipeline using 2.5 Flash TTS (3.1 quota still resetting).
Does NOT touch config.py — only patches this process's in-memory model/chunk-size."""
import sys
import functools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agents.tts_agent as tts_agent

tts_agent.GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
_orig_chunk_text = tts_agent._chunk_text
tts_agent._chunk_text = functools.partial(_orig_chunk_text, max_chars=1500)

import scheduler
scheduler.run()
