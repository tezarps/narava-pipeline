import hashlib
import re
import subprocess
import shutil

import soundfile as sf

from config import (
    OUTPUT_DIR,
    KOKORO_VOICE, KOKORO_SPEED, KOKORO_MODEL_PATH, KOKORO_VOICES_PATH,
)

SILENCE_MS = 450
OPENING_SILENCE_MS = 2000   # longer pause between intro and story body
MAX_VOLUME_RANGE_DB = 9
QUALITY_RETRIES = 2
MAX_CHUNK_CHARS = 220

OPENING_MARKER = "and let the ancient world carry you..."

_CHUNK_EXT = "wav"   # Kokoro native output; chunks stored as WAV internally
_OUT_EXT = "mp3"     # final merged file always mp3

_kokoro = None


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
    return _kokoro


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
    """Pull the fixed intro out as its own chunk so a longer silence
    separates it from the story body."""
    idx = text.find(OPENING_MARKER)
    if idx == -1:
        return None, text
    cut = idx + len(OPENING_MARKER)
    return text[:cut].strip(), text[cut:].strip()


def _audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def _segment_mean_volumes(audio_path, n_segments=4):
    duration = _audio_duration(audio_path)
    if duration < 2:
        return []
    seg_len = duration / n_segments
    volumes = []
    for i in range(n_segments):
        result = subprocess.run(
            ["ffmpeg", "-ss", str(i * seg_len), "-t", str(seg_len),
             "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True
        )
        match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", result.stderr)
        if match:
            volumes.append(float(match.group(1)))
    return volumes


def _is_consistent(audio_path):
    volumes = _segment_mean_volumes(audio_path)
    if len(volumes) < 2:
        return True, 0
    spread = max(volumes) - min(volumes)
    return spread <= MAX_VOLUME_RANGE_DB, spread


def _synthesize_chunk(text, out_path, max_quality_retries=QUALITY_RETRIES):
    kokoro = _get_kokoro()
    for attempt in range(max_quality_retries + 1):
        samples, sample_rate = kokoro.create(
            text, voice=KOKORO_VOICE, speed=KOKORO_SPEED, lang="en-us"
        )
        sf.write(str(out_path), samples, sample_rate)
        ok, spread = _is_consistent(out_path)
        if ok:
            return
        if attempt >= max_quality_retries:
            print(f"    Volume drift {spread:.1f}dB persists — accepting best take")
            return
        print(f"    Volume drift {spread:.1f}dB — re-rolling ({attempt+1}/{max_quality_retries})...")


def _merge_with_ffmpeg(chunk_dir, out_path, opening_present):
    chunks = sorted(chunk_dir.glob(f"[0-9][0-9][0-9][0-9].{_CHUNK_EXT}"))

    # Silences at Kokoro's native 24kHz to match chunk sample rate
    kokoro_sr = 24000

    def _make_silence(ms, name):
        path = chunk_dir / name
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r={kokoro_sr}:cl=mono",
            "-t", f"{ms / 1000:.3f}",
            "-c:a", "pcm_s16le", str(path)
        ], capture_output=True, check=True)
        return path

    silence_path = _make_silence(SILENCE_MS, f"silence.{_CHUNK_EXT}")
    opening_silence_path = (
        _make_silence(OPENING_SILENCE_MS, f"silence_opening.{_CHUNK_EXT}")
        if opening_present else None
    )

    concat_file = chunk_dir / "concat.txt"
    lines = []
    for i, chunk in enumerate(chunks):
        lines.append(f"file '{chunk}'")
        if opening_present and i == 0:
            lines.append(f"file '{opening_silence_path}'")
        else:
            lines.append(f"file '{silence_path}'")
    concat_file.write_text("\n".join(lines))

    raw_merged = chunk_dir / f"merged_raw.{_CHUNK_EXT}"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:a", "pcm_s16le",
        str(raw_merged)
    ], capture_output=True, check=True)

    # Single loudnorm pass — -16 LUFS matches YouTube's sleep-content normalization
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_merged),
        "-af", "loudnorm=I=-16:TP=-3.0:LRA=20",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path)
    ], capture_output=True, check=True)


def generate_audio(script_text, topic_id, category=None):
    out_path = OUTPUT_DIR / "audio" / f"{topic_id}.{_OUT_EXT}"
    if out_path.exists() and out_path.stat().st_size > 0:
        mins = _audio_duration(out_path) / 60
        print(f"    TTS: using cached audio (no re-render) → {out_path.name} ({mins:.0f} min)")
        return out_path

    opening, story = _split_opening(script_text)
    chunks = ([opening] if opening else []) + _chunk_text(story)
    total_chars = sum(len(c) for c in chunks)
    print(f"    TTS: {len(chunks)} chunks, ~{total_chars:,} chars")
    print(f"    Voice: Kokoro {KOKORO_VOICE} @ {KOKORO_SPEED}x (local, no API cost)")

    chunk_dir = OUTPUT_DIR / "audio" / f"chunks_{topic_id}"
    script_hash = hashlib.md5(script_text.encode()).hexdigest()[:8]
    hash_file = chunk_dir / ".script_hash"

    if chunk_dir.exists() and hash_file.exists():
        if hash_file.read_text().strip() != script_hash:
            print("    Script changed — clearing cached chunks")
            shutil.rmtree(chunk_dir)

    chunk_dir.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(script_hash)

    for i, chunk in enumerate(chunks):
        out = chunk_dir / f"{i:04d}.{_CHUNK_EXT}"
        if out.exists() and out.stat().st_size > 0:
            print(f"    TTS: {i+1}/{len(chunks)} (cached)")
            continue
        _synthesize_chunk(chunk, out)
        print(f"    TTS: {i+1}/{len(chunks)} done")

    print("    Merging audio...")
    _merge_with_ffmpeg(chunk_dir, out_path, opening_present=bool(opening))
    shutil.rmtree(chunk_dir)

    mins = _audio_duration(out_path) / 60
    print(f"    Audio: {mins:.0f} min → {out_path.name}")
    return out_path
