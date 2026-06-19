import hashlib
import re
import struct
import subprocess
import shutil
import time
import requests
from config import (
    OUTPUT_DIR, ELEVENLABS_API_KEY, ELEVENLABS_MODEL, ELEVENLABS_OUTPUT_FORMAT,
    ELEVENLABS_VOICE_ID, ELEVENLABS_VOICE_SETTINGS,
    COMPARATIVE_VOICE_ID, COMPARATIVE_VOICE_SETTINGS,
)

SILENCE_MS = 450          # gap between ordinary story chunks
OPENING_SILENCE_MS = 2000  # longer pause between the intro and the story itself
MAX_VOLUME_RANGE_DB = 9  # if segments within a chunk differ more than this, re-roll the chunk
QUALITY_RETRIES = 2
OPENING_MARKER = "and let the ancient world carry you..."  # end of script_agent._OPENING

# ElevenLabs' own docs: keep generations under 800-900 chars for expressive,
# dynamic delivery — longer single generations flatten toward monotone. That's
# an UPPER bound, not a quality floor, so chunking down further to ~1-2 sentences
# is safe and gives a silence gap between most sentences instead of only every
# 4-6 sentences (every chunk boundary gets one) — fixes narration sounding "read"
# rather than spoken with natural pauses. Splitting further costs nothing extra —
# billing is per character regardless of chunk count.
MAX_CHUNK_CHARS = 220

# Format-aware plumbing: pcm_* output is headerless raw PCM (needs WAV-wrapping
# and a lossless ffmpeg codec); mp3_* output is already a complete, playable file
# (must NOT be wrapped — wrapping real MP3 bytes in a WAV header produces a
# corrupt file). Whichever ELEVENLABS_OUTPUT_FORMAT is configured, the rest of
# this module follows it automatically instead of assuming one or the other.
_IS_PCM = ELEVENLABS_OUTPUT_FORMAT.startswith("pcm")
_AUDIO_EXT = "wav" if _IS_PCM else "mp3"
_AUDIO_CODEC = "pcm_s16le" if _IS_PCM else "libmp3lame"
_CODEC_ARGS = ["-c:a", _AUDIO_CODEC] if _IS_PCM else ["-c:a", _AUDIO_CODEC, "-b:a", "192k"]


def _voice_for(category):
    """Comparative-mythology episodes use a separate storyteller voice from the
    main single-deity Shelby narration (picked 2026-06-19, see config.py)."""
    if category and category.lower() == "comparative":
        return COMPARATIVE_VOICE_ID, COMPARATIVE_VOICE_SETTINGS, "Rendy"
    return ELEVENLABS_VOICE_ID, ELEVENLABS_VOICE_SETTINGS, "Shelby"


def _chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    sentences = text.replace("\n\n", " ").replace("\n", " ").split(". ")
    chunks, current = [], ""
    for s in sentences:
        candidate = current + s + ". "
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = s + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_opening(text):
    """Pull the fixed Welcome/title/Shelby intro out as its own chunk, so a
    longer silence can separate it from the story instead of running on."""
    idx = text.find(OPENING_MARKER)
    if idx == -1:
        return None, text
    cut = idx + len(OPENING_MARKER)
    return text[:cut].strip(), text[cut:].strip()


def _pcm_to_wav(pcm_bytes, sample_rate=44100, channels=1, bits_per_sample=16):
    """ElevenLabs' pcm_44100 output format is headerless raw 16-bit PCM — wrap it
    in a minimal WAV header so ffmpeg/ffprobe can read it like any normal audio
    file, with zero lossy re-encoding anywhere in the local pipeline."""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_bytes)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample)
    header += b"data" + struct.pack("<I", data_size)
    return header + pcm_bytes


def _audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def _segment_mean_volumes(audio_path, n_segments=4):
    """Mean volume (dB) of N equal time slices — used to detect fade/whisper drift within a chunk."""
    duration = _audio_duration(audio_path)
    if duration < 2:
        return []
    seg_len = duration / n_segments
    volumes = []
    for i in range(n_segments):
        result = subprocess.run(
            ["ffmpeg", "-ss", str(i * seg_len), "-t", str(seg_len), "-i", str(audio_path),
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True
        )
        match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", result.stderr)
        if match:
            volumes.append(float(match.group(1)))
    return volumes


def _is_consistent(audio_path):
    """Reject chunks where volume drifts too much between segments (fade/whisper artifact)."""
    volumes = _segment_mean_volumes(audio_path)
    if len(volumes) < 2:
        return True, 0
    spread = max(volumes) - min(volumes)
    return spread <= MAX_VOLUME_RANGE_DB, spread


def _call_tts(text, voice_id, voice_settings):
    """Single API call — returns a complete, playable audio file's bytes (WAV if
    the configured output format is PCM, raw MP3 bytes as-is otherwise) or raises."""
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": voice_settings,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code}: {resp.text[:300]}")
    return _pcm_to_wav(resp.content) if _IS_PCM else resp.content


def _synthesize_chunk(text, out_path, voice_id, voice_settings, max_api_retries=5, max_quality_retries=QUALITY_RETRIES):
    """Save the RAW chunk as-is — no per-chunk loudnorm. Loudness normalization
    runs once on the full merged file instead; per-chunk normalization on
    clips this short (under ITU-R BS.1770's reliable measurement window)
    produced audible level jumps between chunks once stitched together."""
    delays = [10, 30, 60, 120, 180]
    api_attempt = 0
    quality_attempt = 0

    while True:
        try:
            wav_bytes = _call_tts(text, voice_id, voice_settings)
        except Exception as api_err:
            # Credit/quota exhaustion never resolves itself on retry — fail fast
            # instead of burning ~7 minutes of backoff (10+30+60+120+180s) on a
            # request that will keep failing the same way every time.
            err_text = str(api_err).lower()
            if any(kw in err_text for kw in (
                "quota", "credit", "insufficient", "payment",
                "subscription_required", "not_allowed", "tier",
            )):
                raise RuntimeError(f"TTS quota/credit/plan error (not retrying): {api_err}")
            wait = delays[min(api_attempt, len(delays) - 1)]
            print(f"    API error attempt {api_attempt+1}/{max_api_retries}: {api_err} — wait {wait}s")
            api_attempt += 1
            if api_attempt >= max_api_retries:
                raise RuntimeError(f"TTS API failed after {max_api_retries} attempts: {api_err}")
            time.sleep(wait)
            continue

        out_path.write_bytes(wav_bytes)

        ok, spread = _is_consistent(out_path)
        if ok:
            return

        quality_attempt += 1
        if quality_attempt >= max_quality_retries:
            print(f"    Volume drift {spread:.1f}dB persists after {max_quality_retries} re-rolls — accepting best take")
            return
        print(f"    Volume drift {spread:.1f}dB detected — re-rolling chunk ({quality_attempt}/{max_quality_retries})...")


def _merge_with_ffmpeg(chunk_dir, out_path, opening_present):
    chunks = sorted(chunk_dir.glob(f"[0-9][0-9][0-9][0-9].{_AUDIO_EXT}"))

    def _make_silence(ms, name):
        path = chunk_dir / name
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{ms / 1000:.3f}",
            *_CODEC_ARGS, str(path)
        ], capture_output=True, check=True)
        return path

    silence_path = _make_silence(SILENCE_MS, f"silence.{_AUDIO_EXT}")
    opening_silence_path = _make_silence(OPENING_SILENCE_MS, f"silence_opening.{_AUDIO_EXT}") if opening_present else None

    concat_file = chunk_dir / "concat.txt"
    lines = []
    for i, chunk in enumerate(chunks):
        lines.append(f"file '{chunk}'")
        if opening_present and i == 0:
            lines.append(f"file '{opening_silence_path}'")
        else:
            lines.append(f"file '{silence_path}'")
    concat_file.write_text("\n".join(lines))

    raw_merged = chunk_dir / f"merged_raw.{_AUDIO_EXT}"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        *_CODEC_ARGS,
        str(raw_merged)
    ], capture_output=True, check=True)

    # Single loudness normalization pass over the whole program — far more
    # reliable than 40+ independent per-chunk passes on clips a few seconds long.
    # When ELEVENLABS_OUTPUT_FORMAT is PCM this stays lossless the whole way, with
    # the only lossy encode in the entire pipeline being the final AAC mux into the
    # delivered video (YouTube requires a compressed delivery codec either way).
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_merged),
        "-af", "loudnorm=I=-16:TP=-3.0:LRA=20",
        *_CODEC_ARGS, str(out_path)
    ], capture_output=True, check=True)


def generate_audio(script_text, topic_id, category=None):
    voice_id, voice_settings, voice_label = _voice_for(category)

    opening, story = _split_opening(script_text)
    chunks = ([opening] if opening else []) + _chunk_text(story)
    total_chars = sum(len(c) for c in chunks)
    quality_label = "studio-quality PCM, no compression" if _IS_PCM else "mp3 192kbps (PCM needs ElevenLabs Pro tier)"
    print(f"    TTS: {len(chunks)} chunks, ~{total_chars:,} chars")
    print(f"    Voice: {voice_label} ({ELEVENLABS_MODEL}, {quality_label})")

    chunk_dir = OUTPUT_DIR / "audio" / f"chunks_{topic_id}"
    script_hash = hashlib.md5(script_text.encode()).hexdigest()[:8]
    hash_file = chunk_dir / ".script_hash"

    # If chunk dir exists but was from a different script, wipe it
    if chunk_dir.exists() and hash_file.exists():
        if hash_file.read_text().strip() != script_hash:
            print(f"    Script changed — clearing cached chunks")
            shutil.rmtree(chunk_dir)

    chunk_dir.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(script_hash)

    for i, chunk in enumerate(chunks):
        out = chunk_dir / f"{i:04d}.{_AUDIO_EXT}"
        if out.exists() and out.stat().st_size > 0:
            print(f"    TTS: {i+1}/{len(chunks)} (cached)")
            continue
        _synthesize_chunk(chunk, out, voice_id, voice_settings)
        print(f"    TTS: {i+1}/{len(chunks)} done")
        time.sleep(1)

    print("    Merging audio...")
    out_path = OUTPUT_DIR / "audio" / f"{topic_id}.{_AUDIO_EXT}"
    _merge_with_ffmpeg(chunk_dir, out_path, opening_present=bool(opening))
    shutil.rmtree(chunk_dir)

    mins = _audio_duration(out_path) / 60
    print(f"    Audio: {mins:.0f} min → {out_path.name}")
    return out_path
